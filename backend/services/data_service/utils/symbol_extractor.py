"""
Symbol Extractor - 统一的加密货币符号提取器
所有采集器共用的符号识别和标准化
"""
import re
from typing import List, Set, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("utils.symbol_extractor")


class SymbolCategory(Enum):
    """符号分类"""
    CRYPTO = "crypto"
    STOCK = "stock"
    ETF = "etf"
    UNKNOWN = "unknown"


@dataclass
class ExtractedSymbol:
    """提取的符号"""
    symbol: str
    category: SymbolCategory
    name: Optional[str] = None
    confidence: float = 1.0
    raw_text: Optional[str] = None


class SymbolExtractor:
    """统一的符号提取器
    
    所有采集器共用的符号识别能力
    """
    
    # 加密货币符号映射（包括常见别名）
    CRYPTO_SYMBOLS = {
        "BTC": ["btc", "bitcoin", "比特币", "xbt"],
        "ETH": ["eth", "ethereum", "以太坊"],
        "SOL": ["sol", "solana"],
        "XRP": ["xrp", "ripple"],
        "DOGE": ["doge", "dogecoin", "狗狗币"],
        "ADA": ["ada", "cardano"],
        "AVAX": ["avax", "avalanche"],
        "DOT": ["dot", "polkadot"],
        "MATIC": ["matic", "polygon"],
        "LINK": ["link", "chainlink"],
        "UNI": ["uni", "uniswap"],
        "ATOM": ["atom", "cosmos"],
        "FTM": ["ftm", "fantom"],
        "NEAR": ["near", "near protocol"],
        "APT": ["apt", "aptos"],
        "OP": ["op", "optimism"],
        "ARB": ["arb", "arbitrum"],
        "BNB": ["bnb", "binancecoin", "币安币"],
        "USDT": ["usdt", "tether"],
        "USDC": ["usdc", "usd coin"],
        "PEPE": ["pepe", "pepe coin"],
    }
    
    # ETF 符号
    ETF_SYMBOLS = {
        "IBIT": ["ibit", "ishares bitcoin etf"],
        "FBTC": ["fbtc", "fidelity bitcoin etf"],
        "ARKB": ["arkb", "ark 21shares bitcoin etf"],
        "BITB": ["bitb", "bitwise bitcoin strategy etf"],
        "BTCO": ["btco", "global x bitcoin strategy etf"],
        "BRRR": ["brrr", "valkyrie bitcoin strategy etf"],
        "W BIT": ["wbit", "wisdomtree bitcoin etf"],
        "BITO": ["bito", "proshares bitcoin strategy etf"],
        "ETHF": ["ethf", "fidelity ether etf"],
        "ETHA": ["etha", "ishares ether etf"],
    }
    
    # 股票符号（加密货币相关）
    STOCK_SYMBOLS = {
        "COIN": ["coin", "coinbase"],
        "MSTR": ["mstr", "microstrategy"],
        "MARA": ["mara", "marathon digital"],
        "RIOT": ["riot", "riot platform"],
        "HOOD": ["hood", "robinhood"],
        "CRCL": ["crcl", "cipher mining"],
        "CLSK": ["clsk", "cleanspark"],
        "HUT": ["hut", "hut 8 mining"],
        "BITF": ["bitf", "bitfarms"],
        "HIVE": ["hive", "hive blockchain"],
    }
    
    def __init__(self):
        # 预编译正则表达式
        self._crypto_pattern = self._compile_crypto_pattern()
        self._etf_pattern = self._compile_etf_pattern()
        self._stock_pattern = self._compile_stock_pattern()
        self._common_pattern = self._compile_common_pattern()
    
    def _compile_crypto_pattern(self) -> re.Pattern:
        """编译加密货币匹配模式"""
        all_keywords = []
        for keywords in self.CRYPTO_SYMBOLS.values():
            all_keywords.extend(keywords)
        
        pattern_str = r"\b(" + "|".join(re.escape(kw) for kw in all_keywords) + r")\b"
        return re.compile(pattern_str, re.IGNORECASE)
    
    def _compile_etf_pattern(self) -> re.Pattern:
        """编译 ETF 匹配模式"""
        all_keywords = []
        for keywords in self.ETF_SYMBOLS.values():
            all_keywords.extend(keywords)
        
        pattern_str = r"\b(" + "|".join(re.escape(kw) for kw in all_keywords) + r")\b"
        return re.compile(pattern_str, re.IGNORECASE)
    
    def _compile_stock_pattern(self) -> re.Pattern:
        """编译股票匹配模式"""
        all_keywords = []
        for keywords in self.STOCK_SYMBOLS.values():
            all_keywords.extend(keywords)
        
        pattern_str = r"\b(" + "|".join(re.escape(kw) for kw in all_keywords) + r")\b"
        return re.compile(pattern_str, re.IGNORECASE)
    
    def _compile_common_pattern(self) -> re.Pattern:
        """编译通用符号匹配模式（捕获 $ 开头的符号）"""
        return re.compile(r"\$[A-Z]{2,6}\b", re.IGNORECASE)
    
    def _normalize_text(self, text: str) -> str:
        """标准化文本"""
        return text.lower()
    
    def _find_symbol_match(self, keyword: str, mapping: Dict[str, List[str]]) -> Optional[str]:
        """在映射中查找匹配的符号"""
        keyword_lower = keyword.lower()
        
        for symbol, keywords in mapping.items():
            if keyword_lower in [k.lower() for k in keywords]:
                return symbol
        return None
    
    def extract(
        self,
        text: str,
        categories: Optional[List[SymbolCategory]] = None
    ) -> List[ExtractedSymbol]:
        """从文本中提取符号
        
        Args:
            text: 要搜索的文本
            categories: 限制提取的类别，None表示全部
            
        Returns:
            ExtractedSymbol 列表
        """
        if not text or not text.strip():
            return []
        
        results: List[ExtractedSymbol] = []
        seen_symbols: Set[str] = set()
        text_lower = text.lower()
        
        # 按优先级提取：加密货币 -> ETF -> 股票
        
        # 1. 提取加密货币符号
        if not categories or SymbolCategory.CRYPTO in categories:
            matches = self._crypto_pattern.findall(text_lower)
            
            for match in matches:
                symbol = self._find_symbol_match(match, self.CRYPTO_SYMBOLS)
                
                if symbol and symbol not in seen_symbols:
                    seen_symbols.add(symbol)
                    
                    name = None
                    for s, kws in self.CRYPTO_SYMBOLS.items():
                        if s == symbol:
                            name = kws[1] if len(kws) > 1 else None
                            break
                    
                    results.append(ExtractedSymbol(
                        symbol=symbol,
                        category=SymbolCategory.CRYPTO,
                        name=name,
                        confidence=0.9,
                        raw_text=match
                    ))
        
        # 2. 提取 ETF 符号
        if not categories or SymbolCategory.ETF in categories:
            matches = self._etf_pattern.findall(text_lower)
            
            for match in matches:
                symbol = self._find_symbol_match(match, self.ETF_SYMBOLS)
                
                if symbol and symbol not in seen_symbols:
                    seen_symbols.add(symbol)
                    
                    name = None
                    for s, kws in self.ETF_SYMBOLS.items():
                        if s == symbol:
                            name = kws[1] if len(kws) > 1 else None
                            break
                    
                    results.append(ExtractedSymbol(
                        symbol=symbol,
                        category=SymbolCategory.ETF,
                        name=name,
                        confidence=0.9,
                        raw_text=match
                    ))
        
        # 3. 提取股票符号
        if not categories or SymbolCategory.STOCK in categories:
            matches = self._stock_pattern.findall(text_lower)
            
            for match in matches:
                symbol = self._find_symbol_match(match, self.STOCK_SYMBOLS)
                
                if symbol and symbol not in seen_symbols:
                    seen_symbols.add(symbol)
                    
                    name = None
                    for s, kws in self.STOCK_SYMBOLS.items():
                        if s == symbol:
                            name = kws[1] if len(kws) > 1 else None
                            break
                    
                    results.append(ExtractedSymbol(
                        symbol=symbol,
                        category=SymbolCategory.STOCK,
                        name=name,
                        confidence=0.9,
                        raw_text=match
                    ))
        
        # 4. 提取 $ 开头的通用符号
        if not categories:
            matches = self._common_pattern.findall(text)
            
            for match in matches:
                symbol = match[1:].upper()
                
                if symbol not in seen_symbols:
                    # 检查是否已知符号
                    category = SymbolCategory.UNKNOWN
                    name = None
                    confidence = 0.5
                    
                    if symbol in self.CRYPTO_SYMBOLS:
                        category = SymbolCategory.CRYPTO
                        confidence = 0.8
                    elif symbol in self.ETF_SYMBOLS:
                        category = SymbolCategory.ETF
                        confidence = 0.8
                    elif symbol in self.STOCK_SYMBOLS:
                        category = SymbolCategory.STOCK
                        confidence = 0.8
                    
                    seen_symbols.add(symbol)
                    results.append(ExtractedSymbol(
                        symbol=symbol,
                        category=category,
                        name=name,
                        confidence=confidence,
                        raw_text=match
                    ))
        
        return results
    
    def extract_crypto_only(self, text: str) -> List[str]:
        """只提取加密货币符号"""
        extracted = self.extract(text, [SymbolCategory.CRYPTO])
        return [s.symbol for s in extracted]
    
    def extract_etf_only(self, text: str) -> List[str]:
        """只提取 ETF 符号"""
        extracted = self.extract(text, [SymbolCategory.ETF])
        return [s.symbol for s in extracted]
    
    def is_black_swan_trigger(self, text: str) -> bool:
        """检测是否可能是黑天鹅事件触发词"""
        black_swan_keywords = [
            "hack", "exploit", "attack", "breach",
            "crash", "collapse", "plunge", "plummet",
            "regulation", "ban", "restriction", "crackdown",
            "bankruptcy", "insolvent", "default",
            "sec", "lawsuit", "sued", "investigation",
            "emergency", "crisis", "panic", "contagion",
            "leak", "stolen", "theft", "lost",
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in black_swan_keywords)
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """获取符号的详细信息"""
        symbol_upper = symbol.upper()
        
        if symbol_upper in self.CRYPTO_SYMBOLS:
            return {
                "symbol": symbol_upper,
                "category": "crypto",
                "aliases": self.CRYPTO_SYMBOLS[symbol_upper]
            }
        
        if symbol_upper in self.ETF_SYMBOLS:
            return {
                "symbol": symbol_upper,
                "category": "etf",
                "aliases": self.ETF_SYMBOLS[symbol_upper]
            }
        
        if symbol_upper in self.STOCK_SYMBOLS:
            return {
                "symbol": symbol_upper,
                "category": "stock",
                "aliases": self.STOCK_SYMBOLS[symbol_upper]
            }
        
        return None


# 全局单例
_extractor: Optional[SymbolExtractor] = None

def get_symbol_extractor() -> SymbolExtractor:
    """获取符号提取器单例"""
    global _extractor
    if _extractor is None:
        _extractor = SymbolExtractor()
    return _extractor
