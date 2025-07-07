# hangtap - Cross-Chain Bridge Event Relayer Simulation

This repository contains a Python script that simulates the core component of a cross-chain bridge: an event relayer. It is designed as an architectural showcase, demonstrating a robust, modular, and extensible structure for a real-world decentralized application backend.

## Concept

In a typical lock-and-mint cross-chain bridge, a user `locks` assets (e.g., USDT) in a smart contract on a source chain (e.g., Ethereum). A relayer network is responsible for detecting this `TokensLocked` event. Upon detection, a relayer submits a transaction to a corresponding smart contract on the destination chain (e.g., Polygon) to `mint` an equivalent amount of wrapped assets for the user.

This script simulates the function of a single relayer node. It performs the following tasks:

1.  **Connects** to both a source and a destination blockchain via RPC endpoints.
2.  **Listens** for a specific event (`TokensLocked`) on the source chain's bridge contract.
3.  **Processes** each detected event by constructing, signing, and (simulating) the sending of a corresponding transaction (`mintTokens`) to the destination chain's bridge contract.
4.  **Manages State** by keeping track of the last scanned block to ensure events are processed exactly once and to allow for graceful shutdowns and restarts.

## Code Architecture

The script is architected with a clear separation of concerns, using distinct classes for different responsibilities. This makes the system easier to understand, maintain, and test.

*   `BlockchainConnector`: A utility class responsible for establishing and verifying the connection to a blockchain node. It abstracts away the `web3.py` connection logic.

*   `EventScanner`: The 'ears' of the relayer. This class is solely responsible for querying a range of blocks for specific smart contract events. It takes a connected `web3` instance and contract details, decoupling it from the rest of the application logic.

*   `TransactionProcessor`: The 'hands' of the relayer. It receives event data from the main service, constructs the appropriate transaction for the destination chain, signs it with the relayer's private key, and simulates its submission.

*   `BridgeRelayerService`: The 'brain' of the operation. This orchestrator class initializes and wires together all the other components. It contains the main application loop, manages the state (last scanned block), and handles the overall workflow, including graceful shutdowns.

### Architectural Flow

```
+-----------------------+
| Source Chain (e.g. ETH) |
+-----------+-----------+
            |
            | 1. 'TokensLocked' event is emitted
            v
+-----------+-----------+
|      EventScanner     | (Scans blocks for events)
+-----------+-----------+
            |
            | 2. Event is found and passed on
            v
+-----------+-----------+
|  BridgeRelayerService | (Orchestrates the process)
+-----------+-----------+
            |
            | 3. Event data is sent for processing
            v
+-----------+-----------+
| TransactionProcessor  | (Builds & signs mint tx)
+-----------+-----------+
            |
            | 4. (Simulated) Submits 'mintTokens' transaction
            v
+--------------------------+
| Destination Chain (e.g. Polygon) |
+--------------------------+

```

## How it Works

1.  **Initialization**: When the script starts, the `BridgeRelayerService` is instantiated. It sets up logging, connects to both the source and destination chains using `BlockchainConnector`, and initializes the `EventScanner` and `TransactionProcessor`.
2.  **State Loading**: The service attempts to load its last known state from a local file (`relayer_state.json`). This file contains the last block number it successfully scanned, ensuring the relayer can resume from where it left off.
3.  **Main Loop**: The service enters an infinite `run()` loop.
4.  **Block Range Calculation**: In each iteration, it checks the latest block number on the source chain and defines a block range to scan (e.g., from `last_scanned_block + 1` to `last_scanned_block + 100`). This is done to avoid requesting too much data from the RPC node at once.
5.  **Event Scanning**: It uses the `EventScanner` instance to query the calculated block range for the `TokensLocked` event.
6.  **Transaction Processing**: If any events are found, they are passed one by one to the `TransactionProcessor`. The processor uses the event data to build a `mintTokens` transaction, signs it, and logs the details of the simulated submission.
7.  **State Update**: After scanning a block range, the service updates `last_scanned_block` in memory and saves it to `relayer_state.json`.
8.  **Polling**: The loop then pauses for a configured polling interval (e.g., 30 seconds) before starting the next cycle.
9.  **Graceful Shutdown**: If the user presses `Ctrl+C`, a `KeyboardInterrupt` is caught, the latest state is saved one last time, and the program exits cleanly.

## Usage Example

### 1. Prerequisites

*   Python 3.8+
*   An RPC URL for a source chain (e.g., from Infura, Ankr, or Alchemy for Ethereum).
*   An RPC URL for a destination chain (e.g., for Polygon).

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/your-username/hangtap.git
cd hangtap

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install the required dependencies
pip install -r requirements.txt
```

### 3. Configuration

The script can be configured via environment variables. Create a file named `.env` in the root directory:

```.env
# .env file

# Required: RPC endpoint for the chain to listen on
SOURCE_CHAIN_RPC_URL="https://rpc.ankr.com/eth"

# Required: RPC endpoint for the chain to submit transactions to
DESTINATION_CHAIN_RPC_URL="https://polygon-rpc.com"

# DANGER: For simulation purposes only. Do not use a real key with funds.
RELAYER_PRIVATE_KEY="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

You can also modify the placeholder contract addresses and other settings directly in the `CONFIG` dictionary at the top of `script.py`.

### 4. Running the Script

Execute the script from your terminal:

```bash
python script.py
```

### Expected Output

You will see logs indicating the service's activity:

```
2023-10-27 10:30:00,123 - BridgeRelayerService - [INFO] - Bridge Relayer Service starting up...
2023-10-27 10:30:00,124 - BridgeRelayerService - [INFO] - Loading state from relayer_state.json
2023-10-27 10:30:01,500 - BlockchainConnector - [INFO] - Attempting to connect to Ethereum at https://rpc.ankr.com/eth...
2023-10-27 10:30:02,800 - BlockchainConnector - [INFO] - Successfully connected to Ethereum. Chain ID: 1
2023-10-27 10:30:03,100 - BlockchainConnector - [INFO] - Attempting to connect to Polygon at https://polygon-rpc.com...
2023-10-27 10:30:04,500 - BlockchainConnector - [INFO] - Successfully connected to Polygon. Chain ID: 137
2023-10-27 10:30:04,501 - TransactionProcessor - [INFO] - TransactionProcessor initialized for relayer address: 0x...
2023-10-27 10:30:04,502 - EventScanner - [INFO] - Scanning for 'TokensLocked' events from block 18456701 to 18456800.
# ... if an event is found ...
2023-10-27 10:30:08,200 - EventScanner - [INFO] - Found 1 'TokensLocked' event(s) in the specified block range.
2023-10-27 10:30:08,201 - TransactionProcessor - [INFO] - Processing event from source transaction: 0x...
2023-10-27 10:30:08,202 - TransactionProcessor - [INFO] - Preparing to mint 100.0 tokens (...) for recipient 0x...
2023-10-27 10:30:09,300 - TransactionProcessor - [INFO] - Transaction successfully signed.
2023-10-27 10:30:09,301 - TransactionProcessor - [WARNING] - --- TRANSACTION SUBMISSION SIMULATION ---
2023-10-27 10:30:09,302 - TransactionProcessor - [WARNING] - Submitting transaction to Polygon...
2023-10-27 10:30:10,305 - TransactionProcessor - [INFO] - [SIMULATED] Transaction successfully sent. Simulated Hash: 0x...
# ... loop continues ...
```