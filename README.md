# Meme-Agent
Meme-Agent is an automated trading and monitoring Agent for tokens on the Bsc blockchain. It is designed to discover, monitor, and trade tokens listed on a bonding curve contract, using growth and momentum-based strategies.ts through a companion SDK (Four_sdk) you developed using this agent.The Agent is built with asynchronous Python, leverages Redis for fast state management, and interacts with smart contracts via the [Four_sdk](https://github.com/Freemandaily/FourMeme-sdk-python), which I developed .

---

## Features

- **Automated Token Discovery:**  
  Continuously scans and tracks new tokens listed on the bonding curve.

- **Growth-Based Filtering:**  
  Monitors tokens whose BNB reserve exceeds a configurable threshold, focusing on those with rapid growth.

- **Momentum Trading Strategy:**  
  Buys tokens that show significant growth in BNB deposits over  timeframes (e.g., 10% in 5 minutes).

- **Automated Trade Execution:**  
  Executes buy and sell transactions via smart contracts, with support for slippage and gas management.

- **Trailing Stop-Loss:**  
  Protects profits and limits losses by automatically updating stop-loss levels as token prices rise.

- **Event-Driven Monitoring:**  
  Listens to blockchain events (buy/sell) in real time to manage open positions and react to market changes.

- **Persistent State Management:**  
  Uses Redis to track monitored tokens, trade history, and growth data.

- **Extensible and Modular:**  
  Designed for easy integration of new strategies, risk management rules, and notification systems.

---

## How It Works

1. **Token Discovery:**  
   The Agent fetches  tokens listed on the bonding curve contract using websocket connection for real time update

2. **Filtering:**  
   Tokens with reserves above a set threshold are added to the monitored list.

3. **Growth Analysis:**  
   The Agent periodically checks the growth rate of each monitored token’s BnB reserve, storing historical data.

4. **Trade Signal Generation:**  
   If a token’s growth rate exceeds configured thresholds (e.g., 10% in 5 minutes), the Agent triggers a buy.

5. **Trade Execution:**  
   The Agent buys the token, records the entry price, and sets a trailing stop-loss.

6. **Event Monitoring:**  
   The Agent listens for buy/sell events and updates stop-losses or sells tokens if the price falls below the stop.

7. **State Persistence:**  
   All relevant data (monitored tokens, trade orders, growth history) is stored in Redis  for reliability.

---

## Project Structure

```
FourMeme/
│
├── trade_processor/
│   ├── trade_main.py         # Main trading logic and event handling
│
├── processsor/
│   ├── processorManager.py   # Token discovery and filtering
│   └── curveManager.py       # Bonding curve interaction
│
├── db_connect/
│   └── db_connector.py       # Redis connection and helpers
│
├── utils/
│   └── util.py               # Abi loading
│
├── market_production.py      # Start Market Analysis
|
|__ trade_producton.py        # start Trading Engine
|
|__ client.py                 # Start telegram client
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

## Start 
There 3 different comonent that made up the build

1. **Market Processor**
  ```bash
  python3 market producion.py
  ```

2. **Trading Processor**
  ```bash
  python3 trade_production.py
  ```

3. **client Integration**
  ```bash
  python3 client.py
  ```


## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/freemandaily/FourMeme.git
   cd FourMeme
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Create a `.env` file with your RPC URLs, private key, and any other secrets:
     ```
     RPC_URL=https://your-bsc-node
     WS_URL=wss://your-bsc-node
     PRIVATE_KEY=your_private_key
     ```

---

## Usage

1. **Configure thresholds and parameters** in the relevant Python files or via environment variables.

2. **Run the main trading process:**
   ```bash
   python trade_processor/trade_main.py
   ```

3. **Monitor logs** for trading activity and errors.

---

## Configuration

- **Thresholds:**  
  Adjust buy/sell thresholds and stop-loss parameters in `trade_main.py`.

- **Database:**  
  Redis is used for fast state management. Configure connection details in `db_connector.py`.

- **Token Filtering:**  
  Update filtering logic in `processorManager.py` and `curveManager.py` as needed.

---

## Contributing

Contributions are welcome! Please open issues or pull requests for bug fixes, improvements, or new features.

---

## Troubleshooting


- **Connection errors:**  
  Check your RPC/WS URLs and network connectivity.
- **Trade failures:**  
  Review logs for error messages and ensure your wallet has sufficient funds.

---


- Visit the [Four_sdk](https://github.com/Freemandaily/FourMeme-sdk-python) I created which powers this agent implementations
