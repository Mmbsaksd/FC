"""
FC Trading System — Complete Learnable Parameter Inventory Audit.
Audits every candidate parameter in the FC trading system:
- Parameter Name
- Category / Type
- Current Value
- Trainable? (ML learned weights / coefficients)
- Hyperparameter? (Configured tuning knob)
- Strategy Parameter? (Rules / threshold)
- Risk Parameter? (Sizing, stop, take profit)
- Search Range
- Asset Scope
- Regime Scope
- Time/Session Scope
- Optimization Method
"""

from typing import Dict, Any, List

PARAMETER_INVENTORY: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. MACHINE LEARNING & META-MODEL WEIGHTS (TRAINABLE)
    # -------------------------------------------------------------
    {
        "parameter_name": "meta_model_weight_tech_score_norm",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.22,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_struct_score_norm",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.18,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_cs_strength_diff_zscore",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.18,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "ASSET_CLASS (FOREX)",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_candle_score_norm",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.12,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_regime_is_trending",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.10,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "REGIME_SPECIFIC",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_macro_score_norm",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.08,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_time_is_london_ny_overlap",
        "type": "MODEL_COEFFICIENT",
        "current_value": 0.06,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "LONDON_NY_OVERLAP",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_weight_risk_spread_to_atr_ratio",
        "type": "MODEL_COEFFICIENT",
        "current_value": -0.35,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 0.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_intercept",
        "type": "MODEL_INTERCEPT",
        "current_value": -0.22,
        "trainable": True,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [-2.0, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Empirical Supervised Logistic Fitting (Walk-Forward Train Split)"
    },
    {
        "parameter_name": "meta_model_platt_temperature",
        "type": "CALIBRATION_HYPERPARAMETER",
        "current_value": 3.8,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": False,
        "is_risk_parameter": False,
        "search_range": [1.0, 10.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Brier Score Loss Minimization on Validation Split"
    },

    # -------------------------------------------------------------
    # 2. EVIDENCE AGGREGATION ENGINE WEIGHTS (STRATEGY / HYPERPARAMETER)
    # -------------------------------------------------------------
    {
        "parameter_name": "aggregator_weight_technical",
        "type": "ENGINE_WEIGHT",
        "current_value": 1.2,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.5, 2.5],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_weight_market_structure",
        "type": "ENGINE_WEIGHT",
        "current_value": 1.2,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.5, 2.5],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_weight_currency_strength",
        "type": "ENGINE_WEIGHT",
        "current_value": 1.1,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.0, 2.0],
        "asset_scope": "ASSET_CLASS (FOREX only, 0 for Commodities/Crypto)",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_weight_risk_metrics",
        "type": "ENGINE_WEIGHT",
        "current_value": 1.0,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.5, 2.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_weight_macro",
        "type": "ENGINE_WEIGHT",
        "current_value": 0.8,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.2, 1.5],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_weight_sentiment",
        "type": "ENGINE_WEIGHT",
        "current_value": 0.8,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.2, 1.5],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Grid / Cross-Entropy Optimization"
    },
    {
        "parameter_name": "aggregator_contradiction_penalty",
        "type": "STRATEGY_PARAMETER",
        "current_value": 4.0,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [1.0, 10.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Grid Search on In-Sample Net R"
    },

    # -------------------------------------------------------------
    # 3. STRATEGY THRESHOLDS & GATES
    # -------------------------------------------------------------
    {
        "parameter_name": "min_opportunity_score",
        "type": "STRATEGY_PARAMETER",
        "current_value": 70.0,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [60.0, 80.0],
        "asset_scope": "GLOBAL / ASSET_CLASS",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward Parameter Stability Analysis (Plateau Selection)"
    },
    {
        "parameter_name": "min_ml_probability",
        "type": "STRATEGY_PARAMETER",
        "current_value": 0.40,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [0.35, 0.60],
        "asset_scope": "GLOBAL / ASSET_CLASS",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Walk-Forward ROC Calibration & Net R Maximization"
    },
    {
        "parameter_name": "max_spread_pips",
        "type": "RISK_PARAMETER",
        "current_value": 10.0,
        "trainable": False,
        "is_hyperparameter": False,
        "is_strategy_parameter": False,
        "is_risk_parameter": True,
        "search_range": [2.0, 25.0],
        "asset_scope": "ASSET_CLASS (Forex: 3.5, Commodity: 10.0, Crypto: 25.0)",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Constrained Risk Optimization (Broker Microstructure Empirical Percentile)"
    },

    # -------------------------------------------------------------
    # 4. RISK & TRADE EXECUTION PARAMETERS
    # -------------------------------------------------------------
    {
        "parameter_name": "atr_multiplier_sl",
        "type": "RISK_PARAMETER",
        "current_value": 1.2,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": False,
        "is_risk_parameter": True,
        "search_range": [0.8, 2.5],
        "asset_scope": "ASSET_CLASS (Forex: 1.2, Commodity: 1.5, Crypto: 2.0)",
        "regime_scope": "HIGH_VOLATILITY / LOW_VOLATILITY",
        "time_session_scope": "ALL",
        "optimization_method": "Excursion / MAE Quantile Analysis"
    },
    {
        "parameter_name": "take_profit_1_r_multiple",
        "type": "RISK_PARAMETER",
        "current_value": 1.5,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": False,
        "is_risk_parameter": True,
        "search_range": [1.0, 2.5],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "MFE Distribution Mode Analysis"
    },
    {
        "parameter_name": "take_profit_2_r_multiple",
        "type": "RISK_PARAMETER",
        "current_value": 3.0,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": False,
        "is_risk_parameter": True,
        "search_range": [2.0, 5.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "TRENDING vs RANGING",
        "time_session_scope": "ALL",
        "optimization_method": "MFE Tail Quantile Optimization"
    },
    {
        "parameter_name": "min_rr_threshold",
        "type": "RISK_PARAMETER",
        "current_value": 2.0,
        "trainable": False,
        "is_hyperparameter": False,
        "is_strategy_parameter": True,
        "is_risk_parameter": True,
        "search_range": [1.5, 3.0],
        "asset_scope": "GLOBAL",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Institutional Mathematical Risk Constraint"
    },
    {
        "parameter_name": "max_holding_bars",
        "type": "STRATEGY_PARAMETER",
        "current_value": 20,
        "trainable": False,
        "is_hyperparameter": True,
        "is_strategy_parameter": True,
        "is_risk_parameter": False,
        "search_range": [10, 40],
        "asset_scope": "GLOBAL (Timeframe: 1D = 20 bars / 1 month)",
        "regime_scope": "ALL",
        "time_session_scope": "ALL",
        "optimization_method": "Time-Decay Alpha Horizon Optimization"
    }
]

def get_parameter_inventory() -> List[Dict[str, Any]]:
    """Returns the complete audited parameter inventory."""
    return PARAMETER_INVENTORY

def get_parameters_by_type(ptype: str) -> List[Dict[str, Any]]:
    """Filters parameter inventory by parameter type."""
    return [p for p in PARAMETER_INVENTORY if p["type"] == ptype]

def get_trainable_parameters() -> List[Dict[str, Any]]:
    """Returns all model parameters fitted via ML training algorithms."""
    return [p for p in PARAMETER_INVENTORY if p["trainable"]]

def get_strategy_parameters() -> List[Dict[str, Any]]:
    """Returns all strategy threshold parameters optimized via walk-forward grid."""
    return [p for p in PARAMETER_INVENTORY if p["is_strategy_parameter"]]

def get_risk_parameters() -> List[Dict[str, Any]]:
    """Returns all risk and money management parameters."""
    return [p for p in PARAMETER_INVENTORY if p["is_risk_parameter"]]
