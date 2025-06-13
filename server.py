#!/usr/bin/env python3.10
import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from datetime import datetime, timedelta
import logging
from typing import Tuple, Optional
import warnings
import threading
import json
from flask import Flask, render_template_string, jsonify, request
import plotly.graph_objs as go
import plotly.utils

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ott_alerts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables for dashboard
alerts_history = []
system_status = {'running': False, 'last_scan': None, 'alerts_today': 0}
current_data = {}

# Flask App
app = Flask(__name__)

# Dashboard HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTT Trading Alert Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }
        
        .header h1 {
            color: #2c3e50;
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        
        .status-bar {
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 20px;
        }
        
        .status-item {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            flex: 1;
            min-width: 200px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease;
        }
        
        .status-item:hover {
            transform: translateY(-3px);
        }
        
        .status-item.offline {
            background: linear-gradient(45deg, #f44336, #d32f2f);
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
        }
        
        .card h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.4em;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        .alerts-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .alerts-table th,
        .alerts-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .alerts-table th {
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white;
            font-weight: bold;
        }
        
        .alerts-table tr:hover {
            background-color: #f5f5f5;
        }
        
        .buy-signal {
            background-color: #d4edda !important;
            color: #155724;
            font-weight: bold;
        }
        
        .sell-signal {
            background-color: #f8d7da !important;
            color: #721c24;
            font-weight: bold;
        }
        
        .chart-container {
            height: 400px;
            margin: 20px 0;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white;
        }
        
        .btn-danger {
            background: linear-gradient(45deg, #e74c3c, #c0392b);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        
        select {
            padding: 8px 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            background: white;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .status-bar {
                flex-direction: column;
            }
            
            .controls {
                justify-content: center;
            }
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 OTT Trading Alert Dashboard</h1>
            <div class="status-bar">
                <div class="status-item" id="system-status">
                    <h4>System Status</h4>
                    <p id="status-text">Loading...</p>
                </div>
                <div class="status-item">
                    <h4>Last Scan</h4>
                    <p id="last-scan">Loading...</p>
                </div>
                <div class="status-item">
                    <h4>Alerts Today</h4>
                    <p id="alerts-today">Loading...</p>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>📊 Live Chart</h3>
                <div class="controls">
                    <select id="symbol-select">
                        <option value="^NSEI">NIFTY 50</option>
                        <option value="^BSESN">SENSEX</option>
                        <option value="^NSEBANK">BANK NIFTY</option>
                    </select>
                    <button class="btn btn-primary" onclick="updateChart()">Update Chart</button>
                </div>
                <div id="price-chart" class="chart-container"></div>
            </div>
            
            <div class="card">
                <h3>🎯 Recent Signals</h3>
                <div id="recent-signals">
                    <div class="loading">Loading signals...</div>
                </div>
            </div>
        </div>
        
        <div class="card full-width">
            <h3>📈 Alerts History</h3>
            <div class="controls">
                <button class="btn btn-primary" onclick="refreshAlerts()">Refresh</button>
                <button class="btn btn-danger" onclick="clearAlerts()">Clear History</button>
            </div>
            <div id="alerts-container">
                <div class="loading">Loading alerts...</div>
            </div>
        </div>
    </div>

    <script>
        // Auto-refresh data every 30 seconds
        setInterval(refreshDashboard, 30000);
        
        // Initial load
        refreshDashboard();
        updateChart();
        
        function refreshDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    updateSystemStatus(data);
                })
                .catch(error => console.error('Error:', error));
            
            refreshAlerts();
            refreshSignals();
        }
        
        function updateSystemStatus(data) {
            const statusElement = document.getElementById('system-status');
            const statusText = document.getElementById('status-text');
            const lastScan = document.getElementById('last-scan');
            const alertsToday = document.getElementById('alerts-today');
            
            if (data.running) {
                statusElement.className = 'status-item';
                statusText.textContent = 'Running ✅';
            } else {
                statusElement.className = 'status-item offline';
                statusText.textContent = 'Offline ❌';
            }
            
            lastScan.textContent = data.last_scan || 'Never';
            alertsToday.textContent = data.alerts_today || '0';
        }
        
        function refreshAlerts() {
            fetch('/api/alerts')
                .then(response => response.json())
                .then(data => {
                    displayAlerts(data);
                })
                .catch(error => console.error('Error:', error));
        }
        
        function refreshSignals() {
            fetch('/api/signals')
                .then(response => response.json())
                .then(data => {
                    displaySignals(data);
                })
                .catch(error => console.error('Error:', error));
        }
        
        function displayAlerts(alerts) {
            const container = document.getElementById('alerts-container');
            
            if (alerts.length === 0) {
                container.innerHTML = '<div class="no-data">No alerts yet</div>';
                return;
            }
            
            let html = `
                <table class="alerts-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Signal</th>
                            <th>Price</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            alerts.slice(0, 50).forEach(alert => {
                const signalClass = alert.signal === 'BUY' ? 'buy-signal' : 'sell-signal';
                html += `
                    <tr class="${signalClass}">
                        <td>${alert.timestamp}</td>
                        <td>${alert.symbol}</td>
                        <td>${alert.signal}</td>
                        <td>₹${alert.price.toFixed(2)}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function displaySignals(signals) {
            const container = document.getElementById('recent-signals');
            
            if (signals.length === 0) {
                container.innerHTML = '<div class="no-data">No recent signals</div>';
                return;
            }
            
            let html = '<div style="max-height: 300px; overflow-y: auto;">';
            signals.slice(0, 10).forEach(signal => {
                const signalClass = signal.signal === 'BUY' ? 'buy-signal' : 'sell-signal';
                html += `
                    <div style="padding: 8px; margin: 5px 0; border-radius: 5px;" class="${signalClass}">
                        <strong>${signal.symbol}</strong> - ${signal.signal} at ₹${signal.price.toFixed(2)}
                        <br><small>${signal.timestamp}</small>
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        }
        
        function updateChart() {
            const symbol = document.getElementById('symbol-select').value;
            
            fetch(`/api/chart/${symbol}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('price-chart').innerHTML = 
                            '<div class="no-data">Error loading chart data</div>';
                        return;
                    }
                    
                    const trace1 = {
                        x: data.timestamps,
                        y: data.prices,
                        type: 'scatter',
                        mode: 'lines',
                        name: 'Price',
                        line: { color: '#3498db', width: 2 }
                    };
                    
                    const trace2 = {
                        x: data.timestamps,
                        y: data.ott,
                        type: 'scatter',
                        mode: 'lines',
                        name: 'OTT',
                        line: { color: '#e74c3c', width: 2 }
                    };
                    
                    const layout = {
                        title: `${symbol} - OTT Analysis`,
                        xaxis: { title: 'Time' },
                        yaxis: { title: 'Price' },
                        hovermode: 'x unified',
                        height: 350
                    };
                    
                    Plotly.newPlot('price-chart', [trace1, trace2], layout);
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('price-chart').innerHTML = 
                        '<div class="no-data">Error loading chart</div>';
                });
        }
        
        function clearAlerts() {
            if (confirm('Are you sure you want to clear all alerts?')) {
                fetch('/api/clear-alerts', { method: 'POST' })
                    .then(() => refreshAlerts())
                    .catch(error => console.error('Error:', error));
            }
        }
    </script>
</body>
</html>
"""

# Load configuration
def load_config(config_file='config.json') -> dict:
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {str(e)}")
        raise

def get_stock_data(symbol: str, period: str = "5d", interval: str = "30m") -> Optional[pd.DataFrame]:
    """
    Fetch stock data from Yahoo Finance with error handling
    """
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            logger.warning(f"No data found for symbol: {symbol}")
            return None
            
        if len(data) < 20:
            logger.warning(f"Insufficient data for {symbol}: {len(data)} points")
            return None
            
        data = data.dropna()
        return data
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def calculate_var_function(src: pd.Series, length: int = 5) -> pd.Series:
    """
    Calculate VAR using Pine Script logic
    """
    try:
        valpha = 2 / (length + 1)
        vud1 = pd.Series(np.where(src > src.shift(1), src - src.shift(1), 0), index=src.index)
        vdd1 = pd.Series(np.where(src < src.shift(1), src.shift(1) - src, 0), index=src.index)
        
        vUD = vud1.rolling(window=9, min_periods=1).sum()
        vDD = vdd1.rolling(window=9, min_periods=1).sum()
        
        denominator = vUD + vDD
        vCMO = np.where(denominator != 0, (vUD - vDD) / denominator, 0)
        vCMO = pd.Series(vCMO, index=src.index).fillna(0)
        
        VAR = pd.Series(index=src.index, dtype=float)
        VAR.iloc[0] = src.iloc[0]
        
        for i in range(1, len(src)):
            alpha_factor = valpha * abs(vCMO.iloc[i])
            VAR.iloc[i] = (alpha_factor * src.iloc[i] + (1 - alpha_factor) * VAR.iloc[i-1])
        
        return VAR
    except Exception as e:
        logger.error(f"Error in VAR calculation: {str(e)}")
        return pd.Series(index=src.index, dtype=float)

def calculate_ott(data: pd.DataFrame, length: int = 5, percent: float = 1.5) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate OTT indicator
    """
    try:
        if data is None or data.empty or len(data) < length:
            logger.warning("Insufficient data for OTT calculation")
            empty_series = pd.Series(index=data.index if data is not None else [], dtype=float)
            return empty_series, empty_series, empty_series
        
        src = data['Close'].copy()
        VAR = calculate_var_function(src, length)
        MAvg = VAR.copy()
        
        fark = MAvg * percent * 0.01
        longStop = MAvg - fark
        shortStop = MAvg + fark
        
        longStop_adj = pd.Series(index=data.index, dtype=float)
        shortStop_adj = pd.Series(index=data.index, dtype=float)
        dir_series = pd.Series(index=data.index, dtype=int)
        MT = pd.Series(index=data.index, dtype=float)
        OTT = pd.Series(index=data.index, dtype=float)
        
        longStop_adj.iloc[0] = longStop.iloc[0]
        shortStop_adj.iloc[0] = shortStop.iloc[0]
        dir_series.iloc[0] = 1
        
        for i in range(1, len(data)):
            if pd.notna(MAvg.iloc[i]) and pd.notna(longStop_adj.iloc[i-1]):
                if MAvg.iloc[i] > longStop_adj.iloc[i-1]:
                    longStop_adj.iloc[i] = max(longStop.iloc[i], longStop_adj.iloc[i-1])
                else:
                    longStop_adj.iloc[i] = longStop.iloc[i]
            else:
                longStop_adj.iloc[i] = longStop.iloc[i]
            
            if pd.notna(MAvg.iloc[i]) and pd.notna(shortStop_adj.iloc[i-1]):
                if MAvg.iloc[i] < shortStop_adj.iloc[i-1]:
                    shortStop_adj.iloc[i] = min(shortStop.iloc[i], shortStop_adj.iloc[i-1])
                else:
                    shortStop_adj.iloc[i] = shortStop.iloc[i]
            else:
                shortStop_adj.iloc[i] = shortStop.iloc[i]
            
            if (dir_series.iloc[i-1] == -1 and 
                pd.notna(MAvg.iloc[i]) and pd.notna(shortStop_adj.iloc[i-1]) and
                MAvg.iloc[i] > shortStop_adj.iloc[i-1]):
                dir_series.iloc[i] = 1
            elif (dir_series.iloc[i-1] == 1 and 
                  pd.notna(MAvg.iloc[i]) and pd.notna(longStop_adj.iloc[i-1]) and
                  MAvg.iloc[i] < longStop_adj.iloc[i-1]):
                dir_series.iloc[i] = -1
            else:
                dir_series.iloc[i] = dir_series.iloc[i-1]
        
        for i in range(len(data)):
            MT.iloc[i] = longStop_adj.iloc[i] if dir_series.iloc[i] == 1 else shortStop_adj.iloc[i]
            
            if pd.notna(MAvg.iloc[i]) and pd.notna(MT.iloc[i]):
                if MAvg.iloc[i] > MT.iloc[i]:
                    OTT.iloc[i] = MT.iloc[i] * (200 + percent) / 200
                else:
                    OTT.iloc[i] = MT.iloc[i] * (200 - percent) / 200
            else:
                OTT.iloc[i] = MT.iloc[i]
        
        return MAvg, OTT, dir_series
    
    except Exception as e:
        logger.error(f"Error in OTT calculation: {str(e)}")
        empty_series = pd.Series(index=data.index if data is not None else [], dtype=float)
        return empty_series, empty_series, empty_series

def detect_signals(MAvg: pd.Series, OTT: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """
    Detect buy and sell signals
    """
    try:
        if MAvg.empty or OTT.empty:
            empty_signals = pd.Series([False] * len(MAvg), index=MAvg.index)
            return empty_signals, empty_signals
        
        OTT_shifted = OTT.shift(2)
        buy_signal = (MAvg > OTT_shifted) & (MAvg.shift(1) <= OTT_shifted.shift(1))
        sell_signal = (MAvg < OTT_shifted) & (MAvg.shift(1) >= OTT_shifted.shift(1))
        
        buy_signal = buy_signal.fillna(False)
        sell_signal = sell_signal.fillna(False)
        
        return buy_signal, sell_signal
    
    except Exception as e:
        logger.error(f"Error in signal detection: {str(e)}")
        empty_signals = pd.Series([False] * len(MAvg), index=MAvg.index)
        return empty_signals, empty_signals

def validate_email_settings(email_settings: dict) -> bool:
    """Validate email settings"""
    required_fields = ['email', 'password', 'recipient']
    return all(email_settings.get(field) for field in required_fields)

def send_email_alert(symbol: str, signal_type: str, price: float, email_settings: dict) -> bool:
    """
    Send email alert
    """
    try:
        if not validate_email_settings(email_settings):
            logger.warning("Email settings incomplete")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = email_settings['email']
        msg['To'] = email_settings['recipient']
        msg['Subject'] = f"OTT Alert: {signal_type.upper()} Signal for {symbol}"
        
        body = f"""
        OTT Strategy Alert
        
        Symbol: {symbol}
        Signal: {signal_type.upper()}
        Price: ₹{price:.2f}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        This is an automated alert from your OTT trading system.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(email_settings['smtp_server'], email_settings['smtp_port']) as server:
            server.starttls()
            server.login(email_settings['email'], email_settings['password'])
            text = msg.as_string()
            server.sendmail(email_settings['email'], email_settings['recipient'], text)
        
        logger.info(f"Email alert sent for {symbol} - {signal_type}")
        return True
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False

def add_alert_to_history(symbol: str, signal_type: str, price: float):
    """Add alert to history with deduplication"""
    global alerts_history, system_status
    alert = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'signal': signal_type,
        'price': price
    }
    
    current_time = datetime.now()
    for existing_alert in alerts_history[:5]:
        existing_time = datetime.strptime(existing_alert['timestamp'], '%Y-%m-%d %H:%M:%S')
        if (existing_alert['symbol'] == symbol and 
            existing_alert['signal'] == signal_type and
            (current_time - existing_time).total_seconds() < 300):
            return
    
    alerts_history.insert(0, alert)
    if len(alerts_history) > 100:
        alerts_history = alerts_history[:100]
    
    # Update today's alert count
    today = datetime.now().strftime('%Y-%m-%d')
    today_alerts = [a for a in alerts_history if a['timestamp'].startswith(today)]
    system_status['alerts_today'] = len(today_alerts)

# Flask Routes
@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    return jsonify(system_status)

@app.route('/api/alerts')
def api_alerts():
    return jsonify(alerts_history)

@app.route('/api/signals')
def api_signals():
    # Return recent signals (last 24 hours)
    recent_alerts = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for alert in alerts_history:
        alert_time = datetime.strptime(alert['timestamp'], '%Y-%m-%d %H:%M:%S')
        if alert_time > cutoff_time:
            recent_alerts.append(alert)
    
    return jsonify(recent_alerts[:20])

@app.route('/api/chart/<symbol>')
def api_chart(symbol):
    try:
        data = get_stock_data(symbol, period="5d", interval="30m")
        if data is None or data.empty:
            return jsonify({'error': 'No data available'})
        
        MAvg, OTT, dir_series = calculate_ott(data, 5, 1.5)
        
        # Store current data for dashboard
        current_data[symbol] = {
            'data': data,
            'MAvg': MAvg,
            'OTT': OTT,
            'timestamp': datetime.now()
        }
        
        return jsonify({
            'timestamps': [str(ts) for ts in data.index],
            'prices': data['Close'].tolist(),
            'ott': OTT.tolist()
        })
    except Exception as e:
        logger.error(f"Chart API error: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/api/clear-alerts', methods=['POST'])
def api_clear_alerts():
    global alerts_history
    alerts_history = []
    system_status['alerts_today'] = 0
    return jsonify({'success': True})

def monitoring_loop():
    """Main monitoring loop running in background thread"""
    global system_status
    
    watchlist = [
        "^NSEI",
        "^BSESN",
        "^NSEBANK"
    ]
    
    email_settings = {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "email": "rakesh.msr@gmail.com",
        "password": "oick mmdo veiv dujt",
        "recipient": "niftystockalert@gmail.com",
        "enabled": True
    }
    
    ott_period = 5
    ott_percent = 1.5
    scan_interval = 300
    
    system_status['running'] = True
    logger.info("Starting OTT Alert Monitoring")
    
    while system_status['running']:
        try:
            logger.info(f"Starting new scan at {datetime.now()}")
            alerts_found = 0
            system_status['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for symbol in watchlist:
                try:
                    data = get_stock_data(symbol, period="5d", interval="30m")
                    
                    if data is not None and len(data) > 20:
                        MAvg, OTT, dir_series = calculate_ott(data, ott_period, ott_percent)
                        buy_signals, sell_signals = detect_signals(MAvg, OTT)
                        
                        recent_buy = buy_signals.tail(3).any()
                        recent_sell = sell_signals.tail(3).any()
                        current_price = data['Close'].iloc[-1]
                        
                        if recent_buy:
                            alerts_found += 1
                            logger.info(f"BUY Signal - {symbol} at ₹{current_price:.2f}")
                            add_alert_to_history(symbol, "BUY", current_price)
                            if email_settings.get('enabled', False):
                                send_email_alert(symbol, "BUY", current_price, email_settings)
                        
                        elif recent_sell:
                            alerts_found += 1
                            logger.info(f"SELL Signal - {symbol} at ₹{current_price:.2f}")
                            add_alert_to_history(symbol, "SELL", current_price)
                            if email_settings.get('enabled', False):
                                send_email_alert(symbol, "SELL", current_price, email_settings)
                        
                    else:
                        logger.warning(f"Unable to fetch data for {symbol}")
                    
                    time.sleep(0.5)  # Prevent rate limiting
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {str(e)}")
            
            logger.info(f"Scan completed. Found {alerts_found} alerts.")
            logger.info(f"Sleeping for {scan_interval} seconds...")
            time.sleep(scan_interval)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            time.sleep(60)  # Wait before retrying

def start_dashboard_server():
    """Start the Flask dashboard server"""
    logger.info("Starting dashboard server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

def main():
    """Main function with dashboard integration"""
    try:
        # Start monitoring in background thread
        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        
        # Start dashboard server (this will block)
        start_dashboard_server()
        
    except KeyboardInterrupt:
        logger.info("Shutting down OTT Alert System")
        system_status['running'] = False
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        system_status['running'] = False

if __name__ == "__main__":
    main()
