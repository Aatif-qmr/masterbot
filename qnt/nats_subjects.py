# /Users/aatifquamre/cipher/qnt/nats_subjects.py

SUBJECTS = {
    # M2 publishes → M1 subscribes
    'SENTIMENT': 'qnt.intelligence.sentiment',
    'MACRO':     'qnt.intelligence.macro',
    'HMM':       'qnt.intelligence.regime',
    'ANOMALY':   'qnt.intelligence.anomaly',
    'CALENDAR':  'qnt.intelligence.calendar',
    'ORDERFLOW_LIVE': 'qnt.intelligence.orderflow.live',

    # M1 publishes → M2 subscribes
    'TRADE_OPEN':   'qnt.execution.trade.open',
    'TRADE_CLOSE':  'qnt.execution.trade.close',
    'RISK_EVENT':   'qnt.execution.risk',
    'BOT_STATUS':   'qnt.execution.status',

    # Bidirectional
    'ALERT':    'qnt.alert',
    'COMMAND':  'qnt.command',
}
