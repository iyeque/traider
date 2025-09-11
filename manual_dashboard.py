import asyncio
from aiohttp import web
import json
import logging # Add this line
from bot.trading_stats import LiveTradingStats

class TradingDashboard:
    def __init__(self):
        self.app = web.Application()
        self.app.add_routes([
            web.get('/', self.handle_index),
            web.get('/ws', self.handle_websocket)
        ])
        
    async def handle_index(self, request):
        return web.Response(text='''
        <html>
            <head>
                <title>Trading Dashboard</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #181c20; color: #f3f3f3; margin: 0; padding: 0; }
                    .container { max-width: 800px; margin: 40px auto; background: #23272b; border-radius: 10px; box-shadow: 0 2px 8px #0008; padding: 32px; }
                    h1 { text-align: center; color: #4fd1c5; }
                    .stats { display: flex; justify-content: space-around; margin-bottom: 32px; }
                    .stat { background: #2d333b; border-radius: 8px; padding: 24px 32px; text-align: center; min-width: 120px; }
                    .stat-title { color: #a0aec0; font-size: 1.1em; }
                    .stat-value { font-size: 2em; font-weight: bold; color: #4fd1c5; }
                    .section { margin-top: 32px; }
                    table { width: 100%; border-collapse: collapse; background: #23272b; }
                    th, td { padding: 10px; border-bottom: 1px solid #333; text-align: left; }
                    th { color: #4fd1c5; }
                    tr:last-child td { border-bottom: none; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Trading Dashboard</h1>
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-title">Trades</div>
                            <div class="stat-value" id="trades">0</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Profit</div>
                            <div class="stat-value" id="profit">$0.00</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Win Rate</div>
                            <div class="stat-value" id="win_rate">0%</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Consec. Losses</div>
                            <div class="stat-value" id="consecutive_losses">0</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Active Strategies</div>
                            <div class="stat-value" id="active_strategies">0</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Sentiment</div>
                            <div class="stat-value" id="sentiment">-</div>
                        </div>
                        <div class="stat">
                            <div class="stat-title">Galaxy Score</div>
                            <div class="stat-value" id="galaxy_score">-</div>
                        </div>
                    </div>
                    <div class="section">
                        <h2>Recent Trades</h2>
                        <table>
                            <thead>
                                <tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Profit</th><th>Timestamp</th></tr>
                            </thead>
                            <tbody id="trade_history"></tbody>
                        </table>
                    </div>
                </div>
                <script>
                    const ws = new WebSocket('ws://' + location.host + '/ws');
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        document.getElementById('trades').textContent = data.trades;
                        document.getElementById('profit').textContent = '$' + data.profit.toFixed(2);
                        document.getElementById('win_rate').textContent = (data.win_rate * 100).toFixed(2) + '%';
                        document.getElementById('consecutive_losses').textContent = data.consecutive_losses;
                        document.getElementById('active_strategies').textContent = data.active_strategies;
                        document.getElementById('sentiment').textContent = data.last_sentiment !== null ? data.last_sentiment.toFixed(2) : '-';
                        document.getElementById('galaxy_score').textContent = data.last_galaxy_score !== null ? data.last_galaxy_score : '-';
                        const tbody = document.getElementById('trade_history');
                        tbody.innerHTML = '';
                        (data.trade_history || []).slice(-10).reverse().forEach(trade => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `<td>${trade.symbol}</td><td>${trade.side}</td><td>${trade.quantity}</td><td>${trade.profit}</td><td>${new Date(trade.timestamp).toLocaleString()}</td>`;
                            tbody.appendChild(tr);
                        });
                    };
                </script>
            </body>
        </html>
        ''', content_type='text/html')

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        stats = LiveTradingStats()
        
        # Create a task for sending updates
        send_updates_task = asyncio.create_task(self._send_updates(ws, stats))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # Handle incoming messages if any
                    pass
                elif msg.type == web.WSMsgType.ERROR:
                    logging.error('WebSocket connection closed with exception %s' % ws.exception())
                elif msg.type == web.WSMsgType.CLOSE:
                    logging.info('WebSocket connection closed.')
                    break
        finally:
            # Ensure the send_updates_task is cancelled when the WebSocket connection is closed
            send_updates_task.cancel()
            try:
                await send_updates_task
            except asyncio.CancelledError:
                pass # Task was cancelled as expected
        return ws

    async def _send_updates(self, ws, stats):
        try:
            while True:
                await ws.send_str(json.dumps(stats.get_stats()))
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logging.info("send_updates task cancelled.")
        except Exception as e:
            logging.error(f"Error in send_updates: {e}")

if __name__ == '__main__':
    dashboard = TradingDashboard()
    try:
        web.run_app(dashboard.app, port=8181)
    except KeyboardInterrupt:
        logging.info("Dashboard stopped by user (Ctrl+C).")
    finally:
        pass
