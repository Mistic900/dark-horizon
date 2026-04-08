"""
🚀 FLASH SWAP ARBITRAGE EXECUTOR - PRODUCTION v2.1
Premium monitoring, gas optimization, profit tracking, error recovery
FIX: Unicode encoding pentru Windows
"""

import json
import time
import threading
import logging
import statistics
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from collections import deque
from enum import Enum

from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from web3.exceptions import ContractLogicError, TransactionNotFound

# ═══════════════════════════════════════════════════════════════════
# FIX WINDOWS ENCODING
# ═══════════════════════════════════════════════════════════════════
if sys.platform == "win32":
    # Fix for Windows console encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# ═══════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════
class TxStatus(Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"

class ExecutionMode(Enum):
    MANUAL = "manual"
    AUTO = "auto"
    SIMULATION = "simulation"

# ═══════════════════════════════════════════════════════════════════
# ADVANCED LOGGER - FIX ENCODING
# ═══════════════════════════════════════════════════════════════════
class AdvancedLogger:
    def __init__(self, log_file: str = "flash_swap.log"):
        self.lock = threading.Lock()
        self.log_file = log_file
        self.stats = {
            "simulations": 0,
            "profitable": 0,
            "executions": 0,
            "successful": 0,
            "failed": 0,
            "total_profit": 0,
            "total_gas": 0
        }
        self.history = deque(maxlen=100)
        
        # Setup file logging - FIX ENCODING
        self.logger = logging.getLogger("FlashSwap")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler with UTF-8 encoding
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
    
    def log(self, level: str, msg: str, color: str = ""):
        colors = {
            "RED": "\033[91m", "GREEN": "\033[92m", "YELLOW": "\033[93m",
            "BLUE": "\033[94m", "CYAN": "\033[96m", "MAGENTA": "\033[95m",
            "RESET": "\033[0m"
        }
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        with self.lock:
            try:
                # Console output with colors
                c = colors.get(color, "")
                reset = colors["RESET"]
                msg_formatted = f"{c}[{timestamp}] [{level}] {msg}{reset}"
                print(msg_formatted, flush=True)
            except Exception as e:
                # Fallback if printing fails
                try:
                    print(f"[{timestamp}] [{level}] {msg}", flush=True)
                except:
                    pass
            
            # File logging
            try:
                log_level = getattr(logging, level.upper(), logging.INFO)
                self.logger.log(log_level, msg)
            except Exception as e:
                pass
            
            # Track history
            self.history.append({
                "timestamp": timestamp,
                "level": level,
                "message": msg
            })
    
    def info(self, msg: str): self.log("INFO", msg, "BLUE")
    def success(self, msg: str): self.log("OK", msg, "GREEN")
    def warning(self, msg: str): self.log("WARN", msg, "YELLOW")
    def error(self, msg: str): self.log("ERR", msg, "RED")
    def debug(self, msg: str): self.log("DBG", msg, "CYAN")
    def metric(self, msg: str): self.log("MET", msg, "MAGENTA")
    
    def print_stats(self):
        """Afiseaza statistici cumulative"""
        self.success("=" * 60)
        self.success("STATISTICS")
        self.success("=" * 60)
        self.info(f"Simulations: {self.stats['simulations']}")
        profitable_pct = (self.stats['profitable'] * 100) // max(self.stats['simulations'], 1)
        self.info(f"Profitable: {self.stats['profitable']} ({profitable_pct}%)")
        self.info(f"Executions: {self.stats['executions']}")
        self.info(f"Successful: {self.stats['successful']}")
        self.info(f"Failed: {self.stats['failed']}")
        self.info(f"Total Profit: {self.stats['total_profit']:.6f}")
        self.info(f"Total Gas: {self.stats['total_gas']:.6f} ETH")
        self.success("=" * 60)

logger = AdvancedLogger()

# ═══════════════════════════════════════════════════════════════════
# ADVANCED CACHE WITH STATS
# ═══════════════════════════════════════════════════════════════════
class AdvancedCache:
    def __init__(self, ttl: int = 2):
        self.ttl = ttl
        self.data = {}
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str):
        with self.lock:
            if key in self.data:
                value, timestamp = self.data[key]
                if time.time() - timestamp < self.ttl:
                    self.hits += 1
                    return value
                else:
                    del self.data[key]
            self.misses += 1
            return None
    
    def set(self, key: str, value):
        with self.lock:
            self.data[key] = (value, time.time())
    
    def clear(self):
        with self.lock:
            self.data.clear()
    
    def get_hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

cache = AdvancedCache(ttl=2)

# ═══════════════════════════════════════════════════════════════════
# CONFIG LOADER WITH VALIDATION
# ═══════════════════════════════════════════════════════════════════
class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        with open(config_file, "r", encoding='utf-8') as f:
            self.config = json.load(f)
        self._validate()
    
    def _validate(self):
        """Valideaza configuratia"""
        required = ["rpc_url", "private_key", "contract_address", "chain_id", "flash_swap"]
        for key in required:
            if key not in self.config:
                raise ValueError(f"Missing config: {key}")
        
        flash = self.config["flash_swap"]
        required_flash = ["pool0", "tokenIn", "tokenOut", "amountIn", "fee1"]
        for key in required_flash:
            if key not in flash:
                raise ValueError(f"Missing flash_swap config: {key}")
        
        logger.success("OK Configuration validated")
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def get_flash(self, key: str, default=None):
        return self.config["flash_swap"].get(key, default)

config = ConfigManager()

# ═══════════════════════════════════════════════════════════════════
# WEB3 MANAGER
# ═══════════════════════════════════════════════════════════════════
class Web3Manager:
    def __init__(self, rpc_url: str, wss_url: str, private_key: str, chain_id: int):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        self.chain_id = chain_id
        self.acct = Account.from_key(private_key)
        self.address = self.acct.address
        
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to RPC")
        
        logger.success(f"OK Connected to RPC")
        logger.info(f"  Wallet: {self.address}")
        logger.info(f"  Chain ID: {chain_id}")
    
    def get_balance(self, address: str) -> float:
        """Returneaza balance in ETH"""
        balance_wei = self.w3.eth.get_balance(address)
        return self.w3.from_wei(balance_wei, "ether")
    
    def get_gas_price(self, use_cache: bool = True) -> int:
        if use_cache:
            cached = cache.get("gas_price")
            if cached:
                return cached
        
        price = self.w3.eth.gas_price
        cache.set("gas_price", price)
        return price
    
    def get_nonce(self, use_cache: bool = True) -> int:
        if use_cache:
            cached = cache.get("nonce")
            if cached:
                return cached
        
        nonce = self.w3.eth.get_transaction_count(self.address)
        cache.set("nonce", nonce)
        return nonce
    
    def increment_nonce(self):
        nonce = cache.get("nonce") or self.get_nonce(use_cache=False)
        cache.set("nonce", nonce + 1)
    
    def send_tx(self, tx: dict) -> str:
        """Trimite tranzactie si returneaza hash"""
        signed_tx = self.acct.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
    
    def wait_receipt(self, tx_hash: str, timeout: int = 300, poll_interval: int = 2) -> Optional[dict]:
        """Asteapta receipt cu retry"""
        for attempt in range(max(timeout // poll_interval, 1)):
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return receipt
            except TransactionNotFound:
                pass
            
            if attempt < (timeout // poll_interval) - 1:
                time.sleep(poll_interval)
        
        return None

web3_mgr = Web3Manager(
    config.get("rpc_url"),
    config.get("wss_url", config.get("rpc_url")),
    config.get("private_key"),
    config.get("chain_id")
)

# ═══════════════════════════════════════════════════════════════════
# TOKEN MANAGER
# ═══════════════════════════════════════════════════════════════════
class TokenManager:
    def __init__(self, web3_mgr: Web3Manager):
        self.w3m = web3_mgr
        self.tokens = {}
    
    erc20_abi = [
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}, {"internalType": "address", "name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
    ]
    
    def get_token(self, address: str) -> Contract:
        """Cache token contracts"""
        address = Web3.to_checksum_address(address)
        if address not in self.tokens:
            self.tokens[address] = self.w3m.w3.eth.contract(address=address, abi=self.erc20_abi)
        return self.tokens[address]
    
    def get_decimals(self, address: str) -> int:
        try:
            contract = self.get_token(address)
            return contract.functions.decimals().call()
        except Exception as e:
            logger.warning(f"WARN Decimals error: {str(e)[:60]}")
            return 18
    
    def get_symbol(self, address: str) -> str:
        try:
            contract = self.get_token(address)
            return contract.functions.symbol().call()
        except Exception as e:
            logger.warning(f"WARN Symbol error: {str(e)[:60]}")
            return "UNKNOWN"
    
    def approve(self, token_address: str, spender_address: str, amount: int) -> Optional[dict]:
        """Aproba token cu retry"""
        token_address = Web3.to_checksum_address(token_address)
        spender_address = Web3.to_checksum_address(spender_address)
        
        try:
            allowance = self.get_token(token_address).functions.allowance(
                self.w3m.address, spender_address
            ).call()
            
            if allowance >= amount:
                logger.success(f"OK Allowance OK: {allowance}")
                return None
            
            logger.warning(f"WARN Approving {amount}...")
            
            nonce = web3_mgr.get_nonce()
            gas_price = web3_mgr.get_gas_price()
            
            tx = self.get_token(token_address).functions.approve(
                spender_address, 2**256 - 1
            ).build_transaction({
                "from": self.w3m.address,
                "nonce": nonce,
                "gas": 100000,
                "gasPrice": gas_price,
                "chainId": self.w3m.chain_id
            })
            
            logger.debug(f"DBG Signing approval TX...")
            tx_hash = self.w3m.send_tx(tx)
            logger.info(f"INFO TX: {tx_hash[:16]}...")
            
            receipt = self.w3m.wait_receipt(tx_hash)
            
            if receipt and receipt.status == 1:
                logger.success("OK Approved!")
                web3_mgr.increment_nonce()
                return receipt
            else:
                logger.error("ERR Approval failed")
                return None
        
        except Exception as e:
            logger.error(f"ERR Approval error: {str(e)[:100]}")
            return None

token_mgr = TokenManager(web3_mgr)

# ═══════════════════════════════════════════════════════════════════
# FLASH SWAP EXECUTOR
# ═══════════════════════════════════════════════════════════════════
class FlashSwapExecutor:
    def __init__(self, web3_mgr: Web3Manager, token_mgr: TokenManager, config: ConfigManager):
        self.w3m = web3_mgr
        self.tm = token_mgr
        self.config = config
        
        # Load config
        self.contract_address = Web3.to_checksum_address(config.get("contract_address"))
        self.pool0 = Web3.to_checksum_address(config.get_flash("pool0"))
        self.tokenIn = Web3.to_checksum_address(config.get_flash("tokenIn"))
        self.tokenOut = Web3.to_checksum_address(config.get_flash("tokenOut"))
        self.fee1 = int(config.get_flash("fee1", 10000))
        self.amount_human = int(config.get_flash("amountIn"))
        self.gas_limit = int(config.get_flash("gas_limit", 800000))
        self.min_profit_bps = int(config.get_flash("min_profit_bps", 0))
        
        # Get decimals
        self.decimals_in = self.tm.get_decimals(self.tokenIn)
        self.decimals_out = self.tm.get_decimals(self.tokenOut)
        self.symbol_in = self.tm.get_symbol(self.tokenIn)
        self.symbol_out = self.tm.get_symbol(self.tokenOut)
        
        # Calculate amounts
        self.amountIn = self.amount_human * (10 ** self.decimals_in)
        self.min_profit_amount = int(self.amountIn * self.min_profit_bps / 10000)
        
        # Flash swap ABI
        self.flash_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "pool0", "type": "address"},
                    {"internalType": "uint24", "name": "fee1", "type": "uint24"},
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "flashSwap",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        self.contract = self.w3m.w3.eth.contract(address=self.contract_address, abi=self.flash_abi)
        
        # Execution tracking
        self.execution_lock = threading.Lock()
        self.last_execution_time = 0
        self.execution_cooldown = 15
        
        logger.success("OK Flash Swap Executor initialized")
        logger.info(f"  Token In: {self.symbol_in} ({self.decimals_in} decimals)")
        logger.info(f"  Token Out: {self.symbol_out} ({self.decimals_out} decimals)")
        logger.info(f"  Amount: {self.amount_human}")
        logger.info(f"  Fee1 (buyback): {self.fee1} bps")
        logger.info(f"  Min Profit: {self.min_profit_bps} bps")
    
    def simulate(self) -> Tuple[bool, str]:
        """Simuleaza flash swap"""
        try:
            deadline = int(time.time()) + 300
            self.contract.functions.flashSwap(
                self.pool0,
                self.fee1,
                self.tokenIn,
                self.tokenOut,
                self.amountIn,
                deadline
            ).call({"from": self.w3m.address})
            
            return True, "OK Profitable"
        except ContractLogicError as e:
            error_msg = str(e)
            if "NoProfit" in error_msg:
                return False, "NoProfit - spread insufficient"
            elif "InvalidCallback" in error_msg:
                return False, "InvalidCallback - check pool"
            elif "reentrant" in error_msg.lower():
                return False, "Reentrancy detected - wait"
            else:
                return False, error_msg[:80]
        except Exception as e:
            return False, str(e)[:80]
    
    def execute(self) -> Optional[dict]:
        """Executa flash swap"""
        with self.execution_lock:
            if time.time() - self.last_execution_time < self.execution_cooldown:
                logger.warning(f"WARN Cooldown - wait {self.execution_cooldown}s...")
                return None
            self.last_execution_time = time.time()
        
        logger.info("INFO EXECUTING FLASH SWAP")
        logger.info(f"   Pool0: {self.pool0[:12]}...")
        logger.info(f"   Fee1: {self.fee1} bps")
        
        try:
            deadline = int(time.time()) + 300
            nonce = self.w3m.get_nonce()
            gas_price = self.w3m.get_gas_price()
            
            logger.debug(f"   Nonce: {nonce}, Gas: {gas_price / 10**9:.2f} Gwei")
            
            tx = self.contract.functions.flashSwap(
                self.pool0,
                self.fee1,
                self.tokenIn,
                self.tokenOut,
                self.amountIn,
                deadline
            ).build_transaction({
                "from": self.w3m.address,
                "nonce": nonce,
                "gas": self.gas_limit,
                "gasPrice": gas_price,
                "chainId": self.w3m.chain_id
            })
            
            logger.debug("DBG Signing TX...")
            tx_hash = self.w3m.send_tx(tx)
            logger.success(f"OK Sent: {tx_hash[:16]}...")
            
            logger.info("INFO Waiting confirmation...")
            receipt = self.w3m.wait_receipt(tx_hash)
            
            self.w3m.increment_nonce()
            cache.clear()
            
            if receipt and receipt.status == 1:
                gas_cost_eth = receipt.gasUsed * gas_price / 10**18
                logger.success("OK SUCCESS")
                logger.success(f"   Gas Used: {receipt.gasUsed}")
                logger.success(f"   TX Fee: {gas_cost_eth:.6f} ETH")
                logger.success(f"   Block: {receipt.blockNumber}")
                
                # Update stats
                logger.stats["executions"] += 1
                logger.stats["successful"] += 1
                logger.stats["total_gas"] += gas_cost_eth
                
                return receipt
            else:
                logger.error("ERR Execution failed")
                logger.stats["executions"] += 1
                logger.stats["failed"] += 1
                return None
        
        except Exception as e:
            logger.error(f"ERR Execution error: {str(e)[:150]}")
            logger.stats["executions"] += 1
            logger.stats["failed"] += 1
            return None

executor = FlashSwapExecutor(web3_mgr, token_mgr, config)

# ═══════════════════════════════════════════════════════════════════
# MONITORING ENGINE
# ═══════════════════════════════════════════════════════════════════
class MonitoringEngine:
    def __init__(self, executor: FlashSwapExecutor):
        self.executor = executor
        self.running = False
        self.consecutive_failures = 0
        self.last_block = 0
        self.block_stats = deque(maxlen=100)
    
    def polling_loop(self):
        """Polling loop cu monitoring"""
        logger.info("INFO POLLING MODE started...")
        self.running = True
        self.last_block = web3_mgr.w3.eth.block_number
        
        while self.running:
            try:
                current_block = web3_mgr.w3.eth.block_number
                
                if current_block > self.last_block:
                    logger.debug(f"DBG Block {current_block}")
                    self.last_block = current_block
                    
                    # Simulate
                    profitable, msg = self.executor.simulate()
                    logger.stats["simulations"] += 1
                    
                    if profitable:
                        logger.stats["profitable"] += 1
                        logger.success(f"OK PROFITABLE! {msg}")
                        self.executor.execute()
                        self.consecutive_failures = 0
                    else:
                        self.consecutive_failures += 1
                        if self.consecutive_failures % 10 == 0:
                            logger.debug(f"   Attempts: {self.consecutive_failures}")
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"ERR Polling error: {str(e)[:80]}")
                time.sleep(5)
    
    def start(self):
        """Pornire monitoring"""
        thread = threading.Thread(target=self.polling_loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Oprire monitoring"""
        self.running = False

monitor = MonitoringEngine(executor)

# ═══════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════
class CLI:
    def __init__(self):
        self.commands = {
            "help": self.cmd_help,
            "status": self.cmd_status,
            "balance": self.cmd_balance,
            "simulate": self.cmd_simulate,
            "execute": self.cmd_execute,
            "stats": self.cmd_stats,
            "cache": self.cmd_cache,
            "exit": self.cmd_exit
        }
    
    def cmd_help(self, *args):
        logger.info("Commands:")
        for cmd in self.commands:
            logger.info(f"  {cmd}")
    
    def cmd_status(self, *args):
        logger.success("OK System Status:")
        logger.info(f"  Gas Price: {web3_mgr.get_gas_price() / 10**9:.2f} Gwei")
        logger.info(f"  Nonce: {web3_mgr.get_nonce()}")
        logger.info(f"  Balance: {web3_mgr.get_balance(web3_mgr.address):.6f} ETH")
        logger.info(f"  Block: {web3_mgr.w3.eth.block_number}")
    
    def cmd_balance(self, *args):
        balance = web3_mgr.get_balance(web3_mgr.address)
        logger.success(f"OK Balance: {balance:.6f} ETH")
    
    def cmd_simulate(self, *args):
        profitable, msg = executor.simulate()
        if profitable:
            logger.success(f"OK {msg}")
        else:
            logger.warning(f"WARN {msg}")
    
    def cmd_execute(self, *args):
        executor.execute()
    
    def cmd_stats(self, *args):
        logger.print_stats()
    
    def cmd_cache(self, *args):
        hit_rate = cache.get_hit_rate()
        logger.metric(f"MET Cache Hit Rate: {hit_rate:.1f}%")
        logger.metric(f"MET Hits: {cache.hits}, Misses: {cache.misses}")
    
    def cmd_exit(self, *args):
        logger.warning("WARN Exiting...")
        monitor.stop()
        exit(0)
    
    def run_command(self, cmd: str):
        parts = cmd.strip().split()
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command in self.commands:
            self.commands[command](*args)
        else:
            logger.error(f"ERR Unknown command: {command}")

cli = CLI()

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    logger.success("=" * 60)
    logger.success("OK FLASH SWAP EXECUTOR v2.1 - PREMIUM")
    logger.success("=" * 60)
    
    # Initialization
    logger.info("\nINFO INITIALIZATION:")
    logger.info(f"  Contract: {executor.contract_address[:12]}...")
    logger.info(f"  Pool0: {executor.pool0[:12]}...")
    
    # Test simulation
    logger.info("\nINFO TESTING CONFIGURATION:")
    profitable, msg = executor.simulate()
    if profitable:
        logger.success(f"OK Simulation OK: {msg}")
    else:
        logger.warning(f"WARN Not profitable now: {msg}")
    
    # Approval
    logger.info("\nINFO APPROVAL:")
    token_mgr.approve(executor.tokenIn, executor.contract_address, executor.amountIn)
    
    # Start monitoring
    logger.info("\nINFO STARTING MONITOR:")
    monitor.start()
    
    logger.success("\nOK System ready")
    logger.info("Commands: help, status, balance, simulate, execute, stats, cache, exit\n")
    
    # Interactive mode
    try:
        while True:
            cmd = input(">>> ").strip()
            if cmd:
                cli.run_command(cmd)
    except KeyboardInterrupt:
        logger.warning("\nWARN Shutting down...")
        monitor.stop()
        time.sleep(1)
        logger.print_stats()
        logger.success("OK Stopped")

if __name__ == "__main__":
    main()