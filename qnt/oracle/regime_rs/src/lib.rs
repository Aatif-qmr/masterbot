use pyo3::prelude::*;
use std::fs::File;
use std::io::Read;

// LSTM architecture: input_size=1, hidden_size=64, num_layers=1, num_classes=3
const INPUT_SIZE: usize = 1;
const HIDDEN_SIZE: usize = 64;
const NUM_CLASSES: usize = 3;
const REGIME_LABELS: [&str; 3] = ["BEAR", "RANGING", "BULL"];

struct LstmWeights {
    // LSTM gate weights — layout: [4*H, I] for input, [4*H, H] for hidden
    weight_ih: Vec<f32>, // shape: 4*64 x 1
    weight_hh: Vec<f32>, // shape: 4*64 x 64
    bias_ih: Vec<f32>,   // shape: 4*64
    bias_hh: Vec<f32>,   // shape: 4*64
    // FC layer
    fc_weight: Vec<f32>, // shape: 3 x 64
    fc_bias: Vec<f32>,   // shape: 3
}

fn load_weights(path: &str) -> Result<LstmWeights, String> {
    let mut f = File::open(path).map_err(|e| format!("Cannot open weights file: {e}"))?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).map_err(|e| format!("Read error: {e}"))?;

    let floats: Vec<f32> = buf
        .chunks_exact(4)
        .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .collect();

    // Expected sizes
    let wih_size = 4 * HIDDEN_SIZE * INPUT_SIZE;  // 256
    let whh_size = 4 * HIDDEN_SIZE * HIDDEN_SIZE; // 16384
    let bias_size = 4 * HIDDEN_SIZE;              // 256
    let fc_w_size = NUM_CLASSES * HIDDEN_SIZE;    // 192
    let fc_b_size = NUM_CLASSES;                  // 3
    let expected = wih_size + whh_size + bias_size * 2 + fc_w_size + fc_b_size;

    if floats.len() != expected {
        return Err(format!(
            "Weight file size mismatch: got {} floats, expected {}",
            floats.len(), expected
        ));
    }

    let mut offset = 0;
    let take = |v: &Vec<f32>, off: &mut usize, n: usize| -> Vec<f32> {
        let s = v[*off..*off + n].to_vec();
        *off += n;
        s
    };

    Ok(LstmWeights {
        weight_ih: take(&floats, &mut offset, wih_size),
        weight_hh: take(&floats, &mut offset, whh_size),
        bias_ih:   take(&floats, &mut offset, bias_size),
        bias_hh:   take(&floats, &mut offset, bias_size),
        fc_weight: take(&floats, &mut offset, fc_w_size),
        fc_bias:   take(&floats, &mut offset, fc_b_size),
    })
}

#[inline]
fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}

// Single LSTM step: updates h and c in-place without any allocations
fn lstm_step(
    x: f32, // input_size = 1
    h: &mut [f32; HIDDEN_SIZE],
    c: &mut [f32; HIDDEN_SIZE],
    w: &LstmWeights,
) {
    // gates = W_ih @ x + b_ih + W_hh @ h + b_hh  shape: 4*H
    let mut gates = [0.0f32; 4 * HIDDEN_SIZE];

    for g in 0..4 * HIDDEN_SIZE {
        let mut sum = w.weight_ih[g] * x + w.bias_ih[g] + w.bias_hh[g];
        let offset = g * HIDDEN_SIZE;
        for j in 0..HIDDEN_SIZE {
            sum += w.weight_hh[offset + j] * h[j];
        }
        gates[g] = sum;
    }

    // Split into i, f, g, o gates (PyTorch order) and update c and h in-place
    for j in 0..HIDDEN_SIZE {
        let i_gate = sigmoid(gates[j]);
        let f_gate = sigmoid(gates[HIDDEN_SIZE + j]);
        let g_gate = gates[2 * HIDDEN_SIZE + j].tanh();
        let o_gate = sigmoid(gates[3 * HIDDEN_SIZE + j]);

        c[j] = f_gate * c[j] + i_gate * g_gate;
        h[j] = o_gate * c[j].tanh();
    }
}

// Run 1-layer LSTM over sequence, return final hidden state
fn lstm_forward(returns: &[f32], w: &LstmWeights) -> [f32; HIDDEN_SIZE] {
    let mut h = [0.0f32; HIDDEN_SIZE];
    let mut c = [0.0f32; HIDDEN_SIZE];

    for &r in returns {
        lstm_step(r, &mut h, &mut c, w);
    }
    h
}

// FC layer: logits = W_fc @ h + b_fc
fn fc_forward(h: &[f32; HIDDEN_SIZE], w: &LstmWeights) -> [f32; NUM_CLASSES] {
    let mut logits = [0.0f32; NUM_CLASSES];
    for k in 0..NUM_CLASSES {
        let mut s = w.fc_bias[k];
        let offset = k * HIDDEN_SIZE;
        for j in 0..HIDDEN_SIZE {
            s += w.fc_weight[offset + j] * h[j];
        }
        logits[k] = s;
    }
    logits
}

fn softmax(logits: &[f32; NUM_CLASSES]) -> [f32; NUM_CLASSES] {
    let mut max = logits[0];
    for &val in logits.iter().skip(1) {
        if val > max {
            max = val;
        }
    }

    let mut exps = [0.0f32; NUM_CLASSES];
    let mut sum = 0.0f32;
    for i in 0..NUM_CLASSES {
        exps[i] = (logits[i] - max).exp();
        sum += exps[i];
    }

    let mut probs = [0.0f32; NUM_CLASSES];
    for i in 0..NUM_CLASSES {
        probs[i] = exps[i] / sum;
    }
    probs
}

/// Run LSTM inference from a binary weights file.
/// returns: list of last-20 log returns (f32)
/// weights_path: path to lstm_weights.bin
/// Returns: (current_regime, next_regime, confidence)
/// Note: current_regime is always "UNKNOWN" here — caller should get it from HMM.
/// This function only predicts the *next* regime.
#[pyfunction]
fn lstm_infer(weights_path: &str, returns: Vec<f32>) -> PyResult<(String, String, f32)> {
    let w = load_weights(weights_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    let h = lstm_forward(&returns, &w);
    let logits = fc_forward(&h, &w);
    let probs = softmax(&logits);

    let mut next_idx = 0;
    let mut max_prob = probs[0];
    for i in 1..NUM_CLASSES {
        if probs[i] > max_prob {
            max_prob = probs[i];
            next_idx = i;
        }
    }

    let confidence = (probs[next_idx] * 1000.0).round() / 1000.0;
    let next_regime = REGIME_LABELS[next_idx].to_string();

    Ok(("UNKNOWN".to_string(), next_regime, confidence))
}

#[pymodule]
fn regime_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(lstm_infer, m)?)?;
    Ok(())
}
