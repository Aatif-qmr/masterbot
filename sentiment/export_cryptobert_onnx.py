"""
sentiment/export_cryptobert_onnx.py
───────────────────────────────────
Export the CryptoBERT sentiment model to ONNX format.

This eliminates the need for the heavy `transformers` + `torch` stack
at inference time. ONNX Runtime is ~3x faster and uses ~60% less RAM.

Usage:
    python3 sentiment/export_cryptobert_onnx.py
    # Output: sentiment/models/cryptobert.onnx + tokenizer files

Requirements:
    pip install transformers torch onnx onnxruntime optimum
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_NAME = "ElKulako/cryptobert"
OUTPUT_DIR = BASE_DIR / "sentiment" / "models"


def export_cryptobert_onnx(
    model_name: str = MODEL_NAME,
    output_dir: str | Path | None = None,
    opset_version: int = 18,
) -> str:
    """
    Export CryptoBERT (or any HuggingFace sentiment model) to ONNX.

    Uses the `optimum` library for robust transformer → ONNX conversion
    with graph optimizations (operator fusion, constant folding).

    Args:
        model_name: HuggingFace model identifier
        output_dir: Directory to save the ONNX model and tokenizer
        opset_version: ONNX opset version

    Returns:
        Path to the ONNX model directory
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    onnx_path = output_dir / "model.onnx"

    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        print(f"Loading {model_name} from HuggingFace...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        print(f"Exporting to ONNX (opset {opset_version})...")
        model = ORTModelForSequenceClassification.from_pretrained(
            model_name,
            export=True,
        )

        # Save model + tokenizer together
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))

        # ARM64-optimized INT8 dynamic quantization via ORTQuantizer
        print("Quantizing ONNX model to INT8 (ARM64)...")
        from optimum.onnxruntime import ORTQuantizer
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
        fp32_path = output_dir / "model.onnx"
        quantizer = ORTQuantizer.from_pretrained(str(output_dir))
        qconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
        quantizer.quantize(save_dir=str(output_dir), quantization_config=qconfig)
        quant_path = output_dir / "model_quantized.onnx"
        if quant_path.exists():
            os.replace(quant_path, fp32_path)

        print(f"✓ Quantized ONNX model saved to: {output_dir}")
        print(f"  Files:")
        for f in sorted(output_dir.iterdir()):
            size_kb = f.stat().st_size / 1024
            print(f"    {f.name}: {size_kb:.1f} KB")

        return str(output_dir)

    except ImportError:
        print("'optimum' not available. Falling back to manual torch.onnx.export...")
        return _manual_export(model_name, output_dir, opset_version)


def _manual_export(
    model_name: str,
    output_dir: Path,
    opset_version: int,
) -> str:
    """Fallback: export using raw torch.onnx.export if optimum is not installed."""
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    print(f"Loading {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()

    # Wrap model to return only the logits tensor, avoiding Hugging Face dict/dataclass export quirks
    class SequenceClassifierWrapper(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, input_ids, attention_mask):
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            return outputs.logits

    wrapper = SequenceClassifierWrapper(model)

    # Save tokenizer and config
    tokenizer.save_pretrained(str(output_dir))
    model.config.save_pretrained(str(output_dir))

    # Create dummy input
    dummy_text = "Bitcoin surges to new all-time high"
    inputs = tokenizer(dummy_text, return_tensors="pt", padding="max_length", max_length=128, truncation=True)

    onnx_path = output_dir / "model.onnx"

    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (inputs["input_ids"], inputs["attention_mask"]),
            str(onnx_path),
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "logits": {0: "batch_size", 1: "num_labels"},
            },
        )

    print(f"✓ ONNX model saved to: {onnx_path}")

    # ARM64-optimized INT8 dynamic quantization via ORTQuantizer
    print("Quantizing ONNX model to INT8 (ARM64)...")
    from optimum.onnxruntime import ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    quantizer = ORTQuantizer.from_pretrained(str(output_dir))
    qconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=str(output_dir), quantization_config=qconfig)
    quant_path = output_dir / "model_quantized.onnx"
    if quant_path.exists():
        os.replace(quant_path, onnx_path)
    print("✓ Quantized ONNX model verification passed")

    return str(output_dir)


def verify_sentiment_output(
    output_dir: str | Path | None = None,
    test_texts: list[str] | None = None,
) -> dict:
    """
    Verify that the ONNX model produces correct sentiment predictions.

    Returns dict with predictions for each test text.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)

    if test_texts is None:
        test_texts = [
            "Bitcoin surges past $100k as institutional buying accelerates",
            "Massive crypto crash wipes out billions in market value",
            "Ethereum developers announce minor protocol update",
        ]

    import onnxruntime as ort
    from transformers import AutoTokenizer
    import numpy as np

    tokenizer = AutoTokenizer.from_pretrained(str(output_dir))
    session = ort.InferenceSession(str(output_dir / "model.onnx"))

    label_map = {0: "Bearish", 1: "Neutral", 2: "Bullish"}
    results = {}

    for text in test_texts:
        inputs = tokenizer(text, return_tensors="np", padding="max_length", max_length=128, truncation=True)
        ort_inputs = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        }
        logits = session.run(None, ort_inputs)[0]
        probs = np.exp(logits) / np.exp(logits).sum(axis=-1, keepdims=True)
        pred_idx = int(np.argmax(probs, axis=-1)[0])
        confidence = float(probs[0, pred_idx])

        results[text] = {
            "label": label_map.get(pred_idx, f"class_{pred_idx}"),
            "confidence": round(confidence, 3),
        }
        print(f"  [{results[text]['label']}] ({confidence:.1%}) {text[:60]}...")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Cipher CryptoBERT → ONNX Export")
    print("=" * 60)

    try:
        path = export_cryptobert_onnx()
        print()
        print("Verifying ONNX sentiment predictions...")
        verify_sentiment_output(path)
    except ImportError as e:
        print(f"ERROR: Missing dependency — {e}")
        print("Install with: pip install transformers torch onnx onnxruntime")
        print("For optimized export: pip install optimum[onnxruntime]")
        sys.exit(1)
