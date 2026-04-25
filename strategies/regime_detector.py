import pandas_ta as ta
import numpy as np

def detect_regime(df):
    """
    Detects market regime based on ADX, ATR, and Bollinger Bands.
    Returns the dataframe with a 'regime' column.
    """
    # 1. Calculate Indicators
    # ADX for trend strength
    adx = df.ta.adx(length=14)
    df['adx'] = adx['ADX_14']
    
    # ATR for volatility relative to price
    df['atr'] = df.ta.atr(length=14)
    df['volatility_ratio'] = df['atr'] / df['close']
    
    # Bollinger Bands for range vs volatility
    bb = df.ta.bbands(length=20, std=2)
    df['bb_width'] = (bb['BBU_20_2.0'] - bb['BBL_20_2.0']) / bb['BBM_20_2.0']
    
    # Trend direction indicator
    df['ema_50'] = df.ta.ema(length=50)
    
    # 2. Define Regime Logic
    conditions = [
        # VOLATILE: High BB Width or High ATR ratio (90th percentile)
        (df['bb_width'] > df['bb_width'].rolling(500).quantile(0.9)) | 
        (df['volatility_ratio'] > df['volatility_ratio'].rolling(500).quantile(0.9)),
        
        # TRENDING_UP: ADX > 25 and Price > EMA 50
        (df['adx'] > 25) & (df['close'] > df['ema_50']),
        
        # TRENDING_DOWN: ADX > 25 and Price < EMA 50
        (df['adx'] > 25) & (df['close'] < df['ema_50']),
        
        # RANGING: ADX < 20 or Narrow BB Width
        (df['adx'] < 20) | (df['bb_width'] < df['bb_width'].rolling(500).quantile(0.3))
    ]
    
    choices = ['VOLATILE', 'TRENDING_UP', 'TRENDING_DOWN', 'RANGING']
    
    # Default to RANGING if no condition met
    df['regime'] = np.select(conditions, choices, default='RANGING')
    
    return df
