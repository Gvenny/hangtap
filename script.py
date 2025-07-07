import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional, List

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import BlockNotFound
from dotenv import load_dotenv

# Load environment variables from .env file for sensitive data
load_dotenv()

# --- Configuration ---
# In a real-world application, this would be managed via environment variables,
# a secure vault, or a dedicated configuration management service.
CONFIG = {
    "source_chain": {
        "name": "Ethereum",
        "rpc_url": os.getenv("SOURCE_CHAIN_RPC_URL", "https://rpc.ankr.com/eth"),
        "bridge_contract_address": "0x0000000000000000000000000000000000000001", # Placeholder address
        "event_to_listen": "TokensLocked"
    },
    "destination_chain": {
        "name": "Polygon",
        "rpc_url": os.getenv("DESTINATION_CHAIN_RPC_URL", "https://polygon-rpc.com"),
        "bridge_contract_address": "0x0000000000000000000000000000000000000002", # Placeholder address
        "action_to_perform": "mintTokens"
    },
    "relayer": {
        "private_key": os.getenv("RELAYER_PRIVATE_KEY", "0x" + "a" * 64), # DANGER: For simulation ONLY.
        "polling_interval_seconds": 30,
        "max_blocks_per_scan": 100,
        "initial_scan_block": "latest"
    },
    "state_file": "relayer_state.json"
}

# --- Contract ABI (Simplified for simulation) ---
# This defines the interface of the smart contracts the relayer interacts with.
# In a real project, this would be loaded from a separate JSON ABI file.
BRIDGE_CONTRACT_ABI = json.loads('''
[
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "token", "type": "address"},
            {"indexed": true, "name": "sender", "type": "address"},
            {"indexed": true, "name": "recipient", "type": "address"},
            {"indexed": false, "name": "amount", "type": "uint256"},
            {"indexed": false, "name": "destinationChainId", "type": "uint256"}
        ],
        "name": "TokensLocked",
        "type": "event"
    },
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "sourceTransactionHash", "type": "bytes32"}
        ],
        "name": "mintTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
''')


class BlockchainConnector:
    """Manages the connection to a blockchain node via JSON-RPC."""

    def __init__(self, rpc_url: str, chain_name: str):
        """
        Initializes the connector with the RPC endpoint URL.

        Args:
            rpc_url (str): The HTTP/S or WSS URL of the blockchain node.
            chain_name (str): The name of the chain for logging purposes.
        """
        self.rpc_url = rpc_url
        self.chain_name = chain_name
        self.web3: Optional[Web3] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def connect(self) -> Web3:
        """
        Establishes a connection to the RPC endpoint.
        Raises ConnectionError on failure.

        Returns:
            Web3: An initialized and connected Web3 instance.
        """
        self.logger.info(f"Attempting to connect to {self.chain_name} at {self.rpc_url}...")
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.web3.is_connected():
                raise ConnectionError(f"Failed to connect to {self.chain_name} node.")
            self.logger.info(f"Successfully connected to {self.chain_name}. Chain ID: {self.web3.eth.chain_id}")
            return self.web3
        except Exception as e:
            self.logger.error(f"Connection to {self.chain_name} failed: {e}")
            raise ConnectionError(f"Could not establish connection to {self.chain_name}.") from e

    def get_latest_block_number(self) -> int:
        """
        Fetches the latest block number from the connected node.

        Returns:
            int: The latest block number.
        """
        if not self.web3 or not self.web3.is_connected():
            self.logger.warning("Not connected. Attempting to reconnect...")
            self.connect()
        return self.web3.eth.block_number


class EventScanner:
    """Scans a given blockchain for specific smart contract events."""

    def __init__(self, web3_instance: Web3, contract_address: str, contract_abi: List[Dict[str, Any]]) -> None:
        """
        Initializes the EventScanner.

        Args:
            web3_instance (Web3): A connected Web3 instance.
            contract_address (str): The address of the smart contract to monitor.
            contract_abi (List[Dict[str, Any]]): The ABI of the smart contract.
        """
        self.web3 = web3_instance
        self.contract_address = self.web3.to_checksum_address(contract_address)
        self.contract: Contract = self.web3.eth.contract(address=self.contract_address, abi=contract_abi)
        self.logger = logging.getLogger(self.__class__.__name__)

    def scan_for_events(self, from_block: int, to_block: int, event_name: str) -> List[Dict[str, Any]]:
        """
        Scans a range of blocks for a specific event.

        Args:
            from_block (int): The starting block number for the scan.
            to_block (int): The ending block number for the scan.
            event_name (str): The name of the event to look for (e.g., 'TokensLocked').

        Returns:
            List[Dict[str, Any]]: A list of decoded event logs.
        """
        self.logger.info(f"Scanning for '{event_name}' events from block {from_block} to {to_block}.")
        try:
            event_filter = self.contract.events[event_name].create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            events = event_filter.get_all_entries()
            if events:
                self.logger.info(f"Found {len(events)} '{event_name}' event(s) in the specified block range.")
            return [dict(event) for event in events] # Convert AttributeDict to dict
        except BlockNotFound:
            self.logger.warning(f"Block range [{from_block}-{to_block}] not found. The 'to_block' might be too far in the future.")
            return []
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during event scanning: {e}")
            return []


class TransactionProcessor:
    """Handles the processing of events and simulates transaction submission to the destination chain."""

    def __init__(self, web3_instance: Web3, contract_address: str, contract_abi: List[Dict[str, Any]], private_key: str) -> None:
        """
        Initializes the TransactionProcessor.

        Args:
            web3_instance (Web3): A connected Web3 instance for the destination chain.
            contract_address (str): The address of the destination bridge contract.
            contract_abi (List[Dict[str, Any]]): The ABI of the destination contract.
            private_key (str): The private key of the relayer's wallet. FOR SIMULATION ONLY.
        """
        self.web3 = web3_instance
        self.contract: Contract = self.web3.eth.contract(address=web3_instance.to_checksum_address(contract_address), abi=contract_abi)
        self.private_key = private_key
        self.relayer_address = self.web3.eth.account.from_key(private_key).address
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"TransactionProcessor initialized for relayer address: {self.relayer_address}")

    def process_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Processes a 'TokensLocked' event and simulates a 'mintTokens' transaction.

        Args:
            event_data (Dict[str, Any]): The decoded event log data.

        Returns:
            bool: True if the simulation was successful, False otherwise.
        """
        try:
            tx_hash = event_data['transactionHash'].hex()
            self.logger.info(f"Processing event from source transaction: {tx_hash}")

            # Extract data from the source chain event
            event_args = event_data['args']
            token = event_args['token']
            recipient = event_args['recipient']
            amount = event_args['amount']

            # SIMULATION: In a real system, you would check if this transaction has already been processed.
            self.logger.info(f"Preparing to mint {self.web3.from_wei(amount, 'ether')} tokens ({token}) for recipient {recipient}.")

            # 1. Build the transaction
            # This calls the 'mintTokens' function on the destination contract.
            nonce = self.web3.eth.get_transaction_count(self.relayer_address)
            tx_payload = {
                'from': self.relayer_address,
                'nonce': nonce,
                'gas': 2000000, # A high gas limit for simulation
                'gasPrice': self.web3.eth.gas_price
            }
            
            mint_tx = self.contract.functions.mintTokens(
                token, 
                recipient, 
                amount, 
                event_data['transactionHash'] # Provide source tx hash for idempotency
            ).build_transaction(tx_payload)

            # 2. Sign the transaction
            signed_tx = self.web3.eth.account.sign_transaction(mint_tx, self.private_key)
            self.logger.info("Transaction successfully signed.")

            # 3. Send the transaction (SIMULATED)
            self.logger.warning("--- TRANSACTION SUBMISSION SIMULATION ---")
            self.logger.warning(f"Submitting transaction to {CONFIG['destination_chain']['name']}...")
            # In a real relayer, you would uncomment the following line:
            # tx_receipt = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            # self.logger.info(f"Transaction submitted. Hash: {tx_receipt.hex()}")
            time.sleep(1) # Simulate network latency
            simulated_tx_hash = Web3.keccak(signed_tx.rawTransaction).hex()
            self.logger.info(f"[SIMULATED] Transaction successfully sent. Simulated Hash: {simulated_tx_hash}")

            return True
        except Exception as e:
            self.logger.error(f"Failed to process event and simulate transaction: {e}")
            return False


class BridgeRelayerService:
    """The main orchestrator for the cross-chain bridge relayer service."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the entire relayer service.
        
        Args:
            config (Dict[str, Any]): The global configuration dictionary.
        """
        self.config = config
        self.setup_logging()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.state = self.load_state()
        self.last_scanned_block = self.state.get("last_scanned_block")

        # Setup for Source Chain
        self.source_connector = BlockchainConnector(config['source_chain']['rpc_url'], config['source_chain']['name'])
        self.source_web3 = self.source_connector.connect()

        self.event_scanner = EventScanner(
            self.source_web3,
            config['source_chain']['bridge_contract_address'],
            BRIDGE_CONTRACT_ABI
        )

        # Setup for Destination Chain
        self.dest_connector = BlockchainConnector(config['destination_chain']['rpc_url'], config['destination_chain']['name'])
        self.dest_web3 = self.dest_connector.connect()

        self.tx_processor = TransactionProcessor(
            self.dest_web3,
            config['destination_chain']['bridge_contract_address'],
            BRIDGE_CONTRACT_ABI,
            config['relayer']['private_key']
        )

    def setup_logging(self) -> None:
        """Configures the global logger for the application."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
            stream=sys.stdout
        )

    def load_state(self) -> Dict[str, Any]:
        """Loads the last processed block number from a state file."""
        if os.path.exists(self.config['state_file']):
            with open(self.config['state_file'], 'r') as f:
                self.logger.info(f"Loading state from {self.config['state_file']}")
                return json.load(f)
        return {}

    def save_state(self) -> None:
        """Saves the last processed block number to the state file."""
        self.state['last_scanned_block'] = self.last_scanned_block
        with open(self.config['state_file'], 'w') as f:
            json.dump(self.state, f)
            self.logger.debug(f"Saved state to {self.config['state_file']}: last_scanned_block = {self.last_scanned_block}")

    def run(self) -> None:
        """The main execution loop for the relayer service."""
        self.logger.info("Bridge Relayer Service starting up...")

        if not self.last_scanned_block:
            initial_setting = self.config['relayer']['initial_scan_block']
            if initial_setting == 'latest':
                self.last_scanned_block = self.source_connector.get_latest_block_number()
            else:
                self.last_scanned_block = int(initial_setting)
            self.logger.info(f"No previous state found. Starting scan from block: {self.last_scanned_block}")

        try:
            while True:
                # Determine the block range to scan
                latest_block = self.source_connector.get_latest_block_number()
                from_block = self.last_scanned_block + 1
                
                # To avoid overwhelming the RPC node, scan in chunks
                to_block = min(latest_block, from_block + self.config['relayer']['max_blocks_per_scan'] - 1)

                if from_block > to_block:
                    self.logger.info(f"No new blocks to scan. Current head is {latest_block}. Sleeping...")
                    time.sleep(self.config['relayer']['polling_interval_seconds'])
                    continue
                
                # Scan for events
                events = self.event_scanner.scan_for_events(
                    from_block,
                    to_block,
                    self.config['source_chain']['event_to_listen']
                )

                # Process any found events
                if events:
                    for event in events:
                        self.tx_processor.process_event(event)
                
                # Update state and wait for the next cycle
                self.last_scanned_block = to_block
                self.save_state()
                time.sleep(self.config['relayer']['polling_interval_seconds'])

        except KeyboardInterrupt:
            self.logger.info("Shutdown signal received. Saving state and exiting gracefully.")
            self.save_state()
        except Exception as e:
            self.logger.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)
        finally:
            self.logger.info("Bridge Relayer Service has been shut down.")


if __name__ == '__main__':
    # This entry point initializes and runs the service.
    # It encapsulates the entire logic, making the script executable.
    try:
        relayer_service = BridgeRelayerService(CONFIG)
        relayer_service.run()
    except ConnectionError as e:
        logging.critical(f"Could not start the service due to a connection issue: {e}")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected error prevented the service from starting: {e}")
        sys.exit(1)
