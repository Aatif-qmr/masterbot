use pyo3::prelude::*;
use rayon::prelude::*;

// ──────────────────────────────────────────────────────────────
// Core risk arithmetic — zero-allocation hot-path functions.
// Each function is a direct port of risk_checks.pyx with added
// safety guarantees (no segfaults, no panics on bad input).
// ──────────────────────────────────────────────────────────────

/// Returns drawdown percentage (positive = loss).
/// Equivalent to: ((start - current) / start) * 100.0
///
/// # Safety
/// Returns 0.0 when `start` is zero (division guard).
#[pyfunction]
#[inline]
fn compute_drawdown_pct(current: f64, start: f64) -> f64 {
    if start == 0.0 {
        return 0.0;
    }
    ((start - current) / start) * 100.0
}

/// Returns position size as a percentage of total balance.
/// Equivalent to: (trade_amount / balance) * 100.0
///
/// # Safety
/// Returns 0.0 when `balance` is zero (division guard).
#[pyfunction]
#[inline]
fn compute_position_pct(trade_amount: f64, balance: f64) -> f64 {
    if balance == 0.0 {
        return 0.0;
    }
    (trade_amount / balance) * 100.0
}

/// Returns true if the order rate limit has been exceeded.
#[pyfunction]
#[inline]
fn check_rate_exceeded(trades_last_hour: i32, max_trades_per_hour: i32) -> bool {
    trades_last_hour > max_trades_per_hour
}

/// Counts the number of consecutive losses at the front of `profits`
/// (a list of float profit_ratio values, most-recent first).
/// Returns the count of leading negatives.
#[pyfunction]
fn count_consecutive_losses(profits: Vec<f64>) -> i32 {
    let mut count: i32 = 0;
    for p in profits {
        if p < 0.0 {
            count += 1;
        } else {
            break;
        }
    }
    count
}

// ──────────────────────────────────────────────────────────────
// Extended risk functions — new capabilities not in the Cython
// version, leveraging Rust's thread-safety for cluster-wide
// risk aggregation.
// ──────────────────────────────────────────────────────────────

/// Batch drawdown computation for multiple balances.
/// Useful for computing drawdowns across all 6 bot instances
/// in a single call, avoiding Python loop overhead.
///
/// Returns a Vec of drawdown percentages (positive = loss).
#[pyfunction]
fn batch_compute_drawdowns(current_balances: Vec<f64>, start_balances: Vec<f64>) -> PyResult<Vec<f64>> {
    if current_balances.len() != start_balances.len() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "current_balances and start_balances must have the same length",
        ));
    }

    let results: Vec<f64> = current_balances
        .iter()
        .zip(start_balances.iter())
        .map(|(&current, &start)| {
            if start == 0.0 {
                0.0
            } else {
                ((start - current) / start) * 100.0
            }
        })
        .collect();

    Ok(results)
}

/// Computes the maximum drawdown from a series of balance snapshots.
/// Returns (max_drawdown_pct, peak_value, trough_value).
///
/// Scans the entire balance history in a single O(n) pass.
#[pyfunction]
fn max_drawdown_from_series(balances: Vec<f64>) -> PyResult<(f64, f64, f64)> {
    if balances.is_empty() {
        return Ok((0.0, 0.0, 0.0));
    }

    let mut peak = balances[0];
    let mut max_dd = 0.0_f64;
    let mut dd_peak = balances[0];
    let mut dd_trough = balances[0];

    for &b in &balances {
        if b > peak {
            peak = b;
        }
        let dd = if peak > 0.0 {
            ((peak - b) / peak) * 100.0
        } else {
            0.0
        };
        if dd > max_dd {
            max_dd = dd;
            dd_peak = peak;
            dd_trough = b;
        }
    }

    Ok((max_dd, dd_peak, dd_trough))
}

/// Compute Sharpe ratio from a list of returns.
/// Uses excess returns over risk-free rate (default 0.0).
/// Returns 0.0 if insufficient data or zero standard deviation.
#[pyfunction]
#[pyo3(signature = (returns, risk_free_rate=None))]
fn compute_sharpe_ratio(returns: Vec<f64>, risk_free_rate: Option<f64>) -> f64 {
    let rf = risk_free_rate.unwrap_or(0.0);
    let n = returns.len();
    if n < 2 {
        return 0.0;
    }

    let mean: f64 = returns.iter().sum::<f64>() / n as f64;
    let excess = mean - rf;

    let variance: f64 = returns.iter().map(|&r| (r - mean).powi(2)).sum::<f64>() / (n - 1) as f64;
    let std_dev = variance.sqrt();

    if std_dev == 0.0 {
        return 0.0;
    }

    excess / std_dev
}

/// Batch Kelly multiplier: multiplier = clamp(1.0 + (win_rate - 0.50) * 2.0, floor, ceiling).
/// Uses rayon for parallel execution across all strategies in one call.
#[pyfunction]
#[pyo3(signature = (win_rates, floor=0.5, ceiling=2.0))]
fn kelly_batch(win_rates: Vec<f64>, floor: f64, ceiling: f64) -> PyResult<Vec<f64>> {
    let results: Vec<f64> = win_rates
        .par_iter()
        .map(|&wr| {
            let raw = 1.0 + (wr - 0.50) * 2.0;
            raw.max(floor).min(ceiling)
        })
        .collect();
    Ok(results)
}

/// Returns version information for the Rust risk_checks module.
#[pyfunction]
fn version() -> String {
    format!(
        "risk_checks v{} (Rust/PyO3, compiled {})",
        env!("CARGO_PKG_VERSION"),
        env!("CARGO_PKG_NAME"),
    )
}

// ──────────────────────────────────────────────────────────────
// Module registration
// ──────────────────────────────────────────────────────────────

#[pymodule]
fn risk_checks(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core functions (1:1 parity with Cython)
    m.add_function(wrap_pyfunction!(compute_drawdown_pct, m)?)?;
    m.add_function(wrap_pyfunction!(compute_position_pct, m)?)?;
    m.add_function(wrap_pyfunction!(check_rate_exceeded, m)?)?;
    m.add_function(wrap_pyfunction!(count_consecutive_losses, m)?)?;

    // Extended functions (new Rust-only capabilities)
    m.add_function(wrap_pyfunction!(batch_compute_drawdowns, m)?)?;
    m.add_function(wrap_pyfunction!(max_drawdown_from_series, m)?)?;
    m.add_function(wrap_pyfunction!(compute_sharpe_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(kelly_batch, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;

    Ok(())
}

// ──────────────────────────────────────────────────────────────
// Native Rust tests — run with `cargo test`
// ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_drawdown_pct() {
        let dd = compute_drawdown_pct(48.5, 50.0);
        assert!((dd - 3.0).abs() < 0.01, "Expected ~3.0%, got {dd}");
    }

    #[test]
    fn test_drawdown_pct_zero_start() {
        assert_eq!(compute_drawdown_pct(100.0, 0.0), 0.0);
    }

    #[test]
    fn test_position_pct() {
        let pp = compute_position_pct(6.0, 50.0);
        assert!((pp - 12.0).abs() < 0.01, "Expected 12.0%, got {pp}");
    }

    #[test]
    fn test_position_pct_zero_balance() {
        assert_eq!(compute_position_pct(6.0, 0.0), 0.0);
    }

    #[test]
    fn test_rate_exceeded() {
        assert!(check_rate_exceeded(15, 10));
        assert!(!check_rate_exceeded(5, 10));
        assert!(!check_rate_exceeded(10, 10)); // Equal is NOT exceeded
    }

    #[test]
    fn test_consecutive_losses() {
        assert_eq!(count_consecutive_losses(vec![-0.02, -0.03, -0.015]), 3);
        assert_eq!(count_consecutive_losses(vec![-0.02, 0.03, -0.015]), 1);
        assert_eq!(count_consecutive_losses(vec![0.01, -0.02, -0.03]), 0);
        assert_eq!(count_consecutive_losses(vec![]), 0);
    }

    #[test]
    fn test_batch_drawdowns() {
        let result = batch_compute_drawdowns(
            vec![48.5, 47.0, 50.0],
            vec![50.0, 50.0, 50.0],
        )
        .unwrap();
        assert!((result[0] - 3.0).abs() < 0.01);
        assert!((result[1] - 6.0).abs() < 0.01);
        assert!((result[2] - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_max_drawdown() {
        let (dd, peak, trough) =
            max_drawdown_from_series(vec![100.0, 110.0, 105.0, 95.0, 100.0, 108.0]).unwrap();
        // Peak = 110, Trough = 95, DD = (110-95)/110 * 100 = 13.636%
        assert!((dd - 13.636).abs() < 0.1, "Expected ~13.6%, got {dd}");
        assert!((peak - 110.0).abs() < 0.01);
        assert!((trough - 95.0).abs() < 0.01);
    }

    #[test]
    fn test_sharpe_ratio() {
        let sharpe = compute_sharpe_ratio(vec![0.01, 0.02, -0.005, 0.015, 0.008], None);
        assert!(sharpe > 0.0, "Expected positive Sharpe, got {sharpe}");
    }

    #[test]
    fn test_sharpe_ratio_empty() {
        assert_eq!(compute_sharpe_ratio(vec![], None), 0.0);
        assert_eq!(compute_sharpe_ratio(vec![0.01], None), 0.0);
    }
}
