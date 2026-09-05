from dataclasses import dataclass, field
from typing import List, Dict, Any, Union

@dataclass
class IndicatorDef:
    name: str
    period: int

@dataclass
class ConstantDef:
    value: float

@dataclass
class PriceDef:
    type: str # "open", "high", "low", "close"

@dataclass
class RuleDef:
    left: Dict[str, Any]
    operator: str
    right: Dict[str, Any]

@dataclass
class ConditionsDef:
    operator: str
    rules: List[RuleDef]

@dataclass
class StrategyDef:
    name: str
    version: int
    symbol: str
    timeframe: str
    conditions: ConditionsDef
