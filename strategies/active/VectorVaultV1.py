import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy
import ta
import rust_engine  # Native Rust PyO3 Module!

class VectorVaultV1(IStrategy):
    """
    Institutional-Grade Vector Pattern Matcher.
    Uses native Rust engine to perform ultra-fast Euclidean similarity matching 
    against a historical vault of market states.
    """
    
    INTERFACE_VERSION = 3
    timeframe = '15m'
    
    # ROI table:
    minimal_roi = {
        "0": 0.15,
        "30": 0.05,
        "60": 0.02,
        "120": 0
    }

    # Stoploss:
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Vector Vault Parameters
    VAULT_LOOKBACK = 1000  # Number of historical states to keep in memory
    FORWARD_PREDICTION = 5  # How many candles ahead to check for success
    
    # For caching historical states to avoid recalculating
    historical_matrix = None
    historical_outcomes = None

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Calculate base features for our vector
        dataframe['rsi'] = ta.momentum.rsi(dataframe['close'], window=14)
        macd = ta.trend.macd(dataframe['close'])
        dataframe['macd'] = macd
        
        # Volatility feature
        dataframe['bb_width'] = (
            ta.volatility.bollinger_hband(dataframe['close']) - 
            ta.volatility.bollinger_lband(dataframe['close'])
        ) / dataframe['close']
        
        # Future outcome (did the price go up N candles later?)
        dataframe['future_return'] = dataframe['close'].shift(-self.FORWARD_PREDICTION) / dataframe['close'] - 1
        
        # Drop NaN
        dataframe.fillna(0, inplace=True)
        
        # Feature columns that make up our "State Vector"
        feature_cols = ['rsi', 'macd', 'bb_width']
        
        # Convert to numpy arrays for fast row-based access
        feature_matrix = dataframe[feature_cols].values.astype(np.float64)
        future_returns = dataframe['future_return'].values
        
        # Create an empty array for the similarity score
        rust_predictions = np.zeros(len(dataframe))
        
        # Iterate over all rows of the dataframe to calculate predictions
        # For each candle i, the historical vault contains data up to i - FORWARD_PREDICTION
        for i in range(len(dataframe)):
            end_idx = i - self.FORWARD_PREDICTION
            if end_idx <= 0:
                continue
            
            # Limit the historical lookback to VAULT_LOOKBACK
            start_idx = max(0, end_idx - self.VAULT_LOOKBACK)
            hist_matrix = feature_matrix[start_idx:end_idx]
            hist_outcomes = future_returns[start_idx:end_idx]
            
            if len(hist_matrix) > 0:
                current_vec = feature_matrix[i]
                try:
                    # RUST NATIVE CALL (Ultra-fast Euclidean parallel matching)
                    best_idx, min_dist = rust_engine.find_closest_match(current_vec, hist_matrix)
                    
                    # Store the predicted return
                    rust_predictions[i] = hist_outcomes[best_idx]
                except Exception as e:
                    print(f"Rust Engine Error at index {i}: {e}")
        
        dataframe['rust_prediction'] = rust_predictions
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                # If the most mathematically similar historical moment resulted in a >1% profit
                (dataframe['rust_prediction'] > 0.01) & 
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                # If the most similar historical moment resulted in a crash
                (dataframe['rust_prediction'] < -0.01) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1

        return dataframe
