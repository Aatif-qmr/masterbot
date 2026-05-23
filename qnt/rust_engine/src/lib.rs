use pyo3::prelude::*;
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use rayon::prelude::*;

/// Finds the closest historical pattern (vector) to the current pattern.
/// Returns a tuple containing the (index of the closest match, the distance score).
#[pyfunction]
fn find_closest_match(
    current_vector: PyReadonlyArray1<f64>,
    historical_matrix: PyReadonlyArray2<f64>,
) -> PyResult<(usize, f64)> {
    // Convert Python numpy arrays to ndarray views
    let current = current_vector.as_array();
    let hist_view = historical_matrix.as_array();

    // Iterate over rows of the historical matrix in parallel using Rayon
    let (best_index, min_distance_sq) = hist_view
        .outer_iter()
        .into_par_iter()
        .enumerate()
        .map(|(idx, hist_row)| {
            // Calculate squared Euclidean distance (avoids expensive sqrt calls in parallel loop)
            let dist_sq = hist_row.iter()
                .zip(current.iter())
                .map(|(x, y)| (x - y).powi(2))
                .sum::<f64>();
            (idx, dist_sq)
        })
        .reduce(
            || (0, f64::MAX),
            |acc, item| {
                if item.1 < acc.1 { item } else { acc }
            },
        );

    // Compute square root only once for the final closest match
    Ok((best_index, min_distance_sq.sqrt()))
}

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
fn rust_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(find_closest_match, m)?)?;
    Ok(())
}
