from __future__ import annotations

import re
import time
import unicodedata

from agentsentry.schemas import RiskSignal, SourceType

CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "і": "i",
        "Α": "A",
        "О": "O",
        "Ε": "E",
    }
)
SECRET_PATTERNS = [
    re.compile(r"CANARY_SECRET_[A-Za-z0-9_-]+", re.I),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
        re.I,
    ),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{20,})\b"),
    re.compile(
        r"(?i)(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"]?([^\s'\",;]{6,})"
    ),
]
INJECTION_PATTERNS = [
    (
        "INSTRUCTION_OVERRIDE",
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|忽略.{0,8}(?:指令|规则)|无视.{0,8}(?:指令|规则)",
    ),
    (
        "ROLE_SPOOFING",
        r"(?:system|developer)\s*(?:message|prompt|override)|you are now|系统(?:指令|消息)|管理员(?:已批准|授权)|用户已经批准",
    ),
    ("CREDENTIAL_THEFT", r"(?:id_rsa|id_ed25519|\.ssh/|private key|私钥|服务器密钥)"),
    (
        "EXFILTRATION_INSTRUCTION",
        r"(?:upload|send|post|exfiltrat|上传|发送|外发).{0,70}(?:secret|credential|token|private|密钥|凭据)|(?:secret|密钥|凭据).{0,50}(?:上传|发送|外发)",
    ),
    (
        "PERSISTENT_INSTRUCTION",
        r"(?:always|from now on|remember to|以后|永久|每次).{0,80}(?:upload|send|execute|ignore|上传|发送|执行|忽略)",
    ),
]


def normalize(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Canonical detector view with source spans; never modifies execution arguments."""
    if text.isascii():
        # ASCII needs only case conversion and whitespace folding, not Unicode per-character work.
        pieces = []
        positions = []
        for match in re.finditer(r"\s+|\S+", text):
            a, b = match.span()
            value = match.group()
            if value[0].isspace():
                pieces.append(" ")
                positions.append((a, b))
            else:
                pieces.append(value.lower())
                positions.extend((i, i + 1) for i in range(a, b))
        return "".join(pieces), positions
    out: list[str] = []
    spans: list[tuple[int, int]] = []
    groups: list[tuple[str, int, int]] = []
    for i, ch in enumerate(text):
        if unicodedata.combining(ch) and groups:
            raw, start, _ = groups[-1]
            groups[-1] = (raw + ch, start, i + 1)
        else:
            groups.append((ch, i, i + 1))
    for raw, start, end in groups:
        if all(unicodedata.category(ch) == "Cf" for ch in raw):
            continue
        canonical = unicodedata.normalize("NFKC", raw).translate(CONFUSABLES).casefold()
        for ch in canonical:
            if unicodedata.category(ch) == "Cf":
                continue
            if ch.isspace():
                if out and out[-1] == " ":
                    spans[-1] = (spans[-1][0], end)
                    continue
                ch = " "
            out.append(ch)
            spans.append((start, end))
    return "".join(out), spans


def secret_labels(text: str) -> list[str]:
    return ["SECRET"] if any(p.search(text) for p in SECRET_PATTERNS) else []


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if re.search(
                r"(?i)^(authorization|cookie|password|token|signature|api_key|secret)$",
                k,
            )
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            value = pattern.sub("[REDACTED:SECRET]", value)
        return value
    return value


class Scanner:
    def __init__(self, model_path: str | None = None):
        self.patterns = [
            (kind, re.compile(pattern, re.I)) for kind, pattern in INJECTION_PATTERNS
        ]
        self.pipeline = None
        self.model_load_error = False
        self.model_version = "rules-1.0"
        if model_path:
            try:
                from transformers import (
                    AutoTokenizer,
                    AutoModelForSequenceClassification,
                    pipeline,
                )
                from pathlib import Path
                import hashlib

                root = Path(model_path)
                tokenizer = AutoTokenizer.from_pretrained(
                    root, local_files_only=True, trust_remote_code=False
                )
                model = AutoModelForSequenceClassification.from_pretrained(
                    root,
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                )
                mapping = {str(v).upper() for v in model.config.id2label.values()}
                if not mapping & {"INJECTION", "LABEL_1", "1"}:
                    raise ValueError("UNSUPPORTED_CLASSIFIER_LABELS")
                self.pipeline = pipeline(
                    "text-classification", model=model, tokenizer=tokenizer, device=-1
                )
                hashes = []
                for file in sorted(root.glob("*")):
                    if file.is_file():
                        h = hashlib.sha256()
                        with file.open("rb") as f:
                            while block := f.read(1024 * 1024):
                                h.update(block)
                        hashes.append(file.name + ":" + h.hexdigest())
                self.model_version = (
                    "local:" + hashlib.sha256("\n".join(hashes).encode()).hexdigest()
                )
            except Exception:
                self.model_load_error = True
                self.model_version = "configured-model-unavailable"

    def scan(
        self, chunk_id: str, text: str, source: SourceType
    ) -> tuple[str, RiskSignal]:
        start = time.perf_counter()
        if len(text) > 65536:
            raise ValueError("CONTEXT_BUDGET_EXCEEDED")
        view, mapping = normalize(text)
        evidence = []
        types = []
        for kind, pattern in self.patterns:
            for match in list(pattern.finditer(view))[:8]:
                types.append(kind)
                a, b = mapping[match.start()][0], mapping[match.end() - 1][1]
                evidence.append(
                    {
                        "type": kind,
                        "canonical_span": [match.start(), match.end()],
                        "raw_span": [a, b],
                        "text": redact(text[a:b]),
                    }
                )
        labels = secret_labels(text)
        if source != SourceType.USER:
            labels.append("UNTRUSTED_EXTERNAL")
        if types:
            labels.append("INJECTION_RISK")
        if "PERSISTENT_INSTRUCTION" in types:
            labels.append("PERSISTENT_INSTRUCTION")
        score = min(0.99, 0.35 + 0.22 * len(set(types))) if types else 0.03
        if self.pipeline:
            # Token windows preserve every token; no silent truncation between character windows.
            tokens = self.pipeline.tokenizer(view, add_special_tokens=False)[
                "input_ids"
            ]
            if len(tokens) > 4096:
                raise ValueError("MODEL_TOKEN_BUDGET_EXCEEDED")
            for offset in range(0, max(1, len(tokens)), 384):
                chunk = self.pipeline.tokenizer.decode(
                    tokens[offset : offset + 448], skip_special_tokens=True
                )
                result = self.pipeline(chunk, truncation=True, max_length=512)[0]
                model_score = (
                    result["score"]
                    if str(result["label"]).upper() in {"INJECTION", "LABEL_1", "1"}
                    else 1 - result["score"]
                )
                score = max(score, float(model_score))
            if score >= 0.75 and "INJECTION_RISK" not in labels:
                labels.append("INJECTION_RISK")
                types.append("MODEL_INJECTION_SIGNAL")

        risk = (
            "CRITICAL"
            if labels and "SECRET" in labels and "EXFILTRATION_INSTRUCTION" in types
            else "HIGH"
            if score >= 0.75
            else "MEDIUM"
            if score >= 0.4
            else "LOW"
        )
        return view, RiskSignal(
            chunk_id=chunk_id,
            risk=risk,
            score=score,
            attack_types=sorted(set(types)),
            evidence=evidence,
            labels=sorted(set(labels)),
            source_type=source,
            model_version=self.model_version,
            scanned_characters=len(text),
            latency_ms=(time.perf_counter() - start) * 1000,
        )
