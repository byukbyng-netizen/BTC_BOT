"""Simple historical replay for the EMA/ATR strategy."""
from __future__ import annotations
from strategy import EmaAtrStrategy
from paper_engine import PaperEngine

def run_backtest(rows, strategy=None, initial_quote=1000.0):
    strategy = strategy or EmaAtrStrategy()
    engine = PaperEngine(initial_quote=initial_quote)
    signals=[]
    for index in range(1, len(rows)+1):
        result=strategy.evaluate(rows[:index])
        signals.append(result.action)
        price=float(rows[index-1]['close'])
        if engine.position:
            if float(rows[index-1]['low']) <= engine.position.stop_price:
                engine.execute('sell', engine.position.stop_price, reason='stop_loss')
            elif engine.position.take_profit_price and float(rows[index-1]['high']) >= engine.position.take_profit_price:
                engine.execute('sell', engine.position.take_profit_price, reason='take_profit')
        if result.action=='buy': engine.execute('buy', price, risk_amount=initial_quote*0.005, stop_price=result.stop_price, take_profit_price=result.take_profit_price, reason=result.reason)
        elif result.action=='sell': engine.execute('sell', price, reason=result.reason)
        engine.snapshot(price, timestamp=str(rows[index-1].get('timestamp', index)))
    snapshot = engine.snapshot(float(rows[-1]['close'])) if rows else engine.snapshot(0)
    return {**snapshot, **engine.performance(float(rows[-1]['close']) if rows else 0), 'signals': signals, 'trades': engine.trades}
