from flask import Flask, render_template_string
import requests
import json
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# Configurazione avanzata
CONFIG = {
    'API_KEY': "644527349738df0ac9452e2a5f773afd",  # Sostituisci con la tua chiave
    'SPORTS': ["soccer", "tennis", "basketball"],
    'REGIONS': "eu,us,uk,au",
    'MARKETS': ["h2h"],
    'MIN_PROFIT': 0.5,
    'TIMEOUT': 30,
    'BOOKMAKERS': [
        '1xbet', 'bet365', 'betfair', 'bwin', 'pinnacle', 
        'unibet', 'williamhill', 'marathonbet', 'matchbook'
    ],
    'STAKE': 100  # Importo totale da investire
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Surebet Pro</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
        .surebet { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .event-header { display: flex; justify-content: space-between; margin-bottom: 15px; }
        .event-name { font-size: 1.2em; font-weight: bold; color: #2c3e50; }
        .profit-badge { background: #27ae60; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold; }
        .bet-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 15px; }
        .bet-card { background: white; padding: 15px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .bet-type { font-weight: bold; margin-bottom: 8px; color: #e67e22; }
        .bet-odd { font-size: 1.1em; margin: 5px 0; }
        .bet-stake { color: #3498db; font-weight: bold; }
        .bet-bookmaker { color: #9b59b6; margin-top: 5px; font-size: 0.9em; }
        .summary { margin-top: 20px; padding: 15px; background: #ecf0f1; border-radius: 6px; }
    </style>
</head>
<body>
    <h1>Surebet Pro</h1>
    <p>Analisi in tempo reale su {{ bookmakers|length }} bookmaker</p>
    
    {% if error %}
        <div style="color: #e74c3c; padding: 15px; background: #fde8e8; border-radius: 8px; margin-bottom: 20px;">
            {{ error }}
        </div>
    {% endif %}
    
    {% if surebets %}
        {% for bet in surebets %}
        <div class="surebet">
            <div class="event-header">
                <div class="event-name">{{ bet.sport|upper }}: {{ bet.event }}</div>
                <div class="profit-badge">{{ bet.profit }}% PROFITTO</div>
            </div>
            
            <div class="bet-grid">
                {% for outcome in bet.details %}
                <div class="bet-card">
                    <div class="bet-type">{{ outcome.outcome }}</div>
                    <div class="bet-odd">Quota: {{ outcome.odd }}</div>
                    <div class="bet-stake">Punta: €{{ outcome.stake }}</div>
                    <div class="bet-bookmaker">Su: {{ outcome.bookmaker }}</div>
                    <div style="margin-top: 10px; font-size: 0.9em;">
                        Ritorno: €{{ outcome.return }}
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="summary">
                <div><strong>Investimento totale:</strong> €{{ bet.total_stake }}</div>
                <div><strong>Ritorno garantito:</strong> €{{ bet.guaranteed_return }}</div>
                <div><strong>Profitto:</strong> €{{ bet.profit_value }} ({{ bet.profit }}%)</div>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div style="text-align: center; padding: 40px; background: #f8f9fa; border-radius: 8px; margin-top: 30px;">
            <h3>Nessuna surebet trovata con profitto > {{ min_profit }}%</h3>
            <p>Ultimo aggiornamento: {{ last_updated }}</p>
        </div>
    {% endif %}
</body>
</html>
"""

def get_odds(sport, is_live=False):
    """Recupera le quote dall'API con gestione errori avanzata"""
    endpoint = "live" if is_live else "odds"
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/{endpoint}"
    
    params = {
        'apiKey': CONFIG['API_KEY'],
        'regions': CONFIG['REGIONS'],
        'markets': ','.join(CONFIG['MARKETS']),
        'oddsFormat': 'decimal',
        'bookmakers': ','.join(CONFIG['BOOKMAKERS'])
    }
    
    try:
        response = requests.get(url, params=params, timeout=CONFIG['TIMEOUT'])
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Errore API: {str(e)}"
    except Exception as e:
        return None, f"Errore sconosciuto: {str(e)}"

def calculate_stakes(odds, total_stake):
    """Calcola gli importi ottimali da puntare"""
    total = sum(1.0 / odd for odd in odds.values())
    return {outcome: round((total_stake / odd) / total, 2) for outcome, odd in odds.items()}

def find_surebets(odds_data, sport, is_live=False):
    """Analizza i dati per trovare surebet con puntate precise"""
    surebets = []
    
    for event in odds_data:
        if not isinstance(event, dict):
            continue
        
        # Estrai nome evento
        home_team = event.get('home_team', 'Home')
        away_team = event.get('away_team', 'Away')
        event_name = f"{home_team} vs {away_team}"
        
        # Trova le migliori quote per ogni bookmaker
        best_odds = defaultdict(dict)
        bookmakers_used = defaultdict(dict)
        
        for bookmaker in event.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                if market['key'] != 'h2h':
                    continue
                
                for outcome in market.get('outcomes', []):
                    outcome_name = outcome.get('name', '')
                    odd = float(outcome.get('price', 1.0))
                    
                    if (outcome_name not in best_odds[market['key']] or 
                        odd > best_odds[market['key']][outcome_name]['odd']):
                        best_odds[market['key']][outcome_name] = {
                            'odd': odd,
                            'bookmaker': bookmaker.get('title', 'Unknown')
                        }
        
        # Analizza ogni mercato
        for market_type, outcomes in best_odds.items():
            if len(outcomes) >= 2:  # Almeno 2 possibili risultati
                total_inversion = sum(1.0 / o['odd'] for o in outcomes.values())
                
                if total_inversion < 1.0:
                    profit = (1.0 - total_inversion) * 100
                    if profit >= CONFIG['MIN_PROFIT']:
                        # Calcola puntate ottimali
                        odds = {k: v['odd'] for k, v in outcomes.items()}
                        stakes = calculate_stakes(odds, CONFIG['STAKE'])
                        
                        # Prepara dettagli per la visualizzazione
                        details = []
                        for outcome, data in outcomes.items():
                            stake = stakes.get(outcome, 0)
                            details.append({
                                'outcome': {
                                    'Home': '1 - Vittoria Casa',
                                    'Draw': 'X - Pareggio',
                                    'Away': '2 - Vittoria Ospite'
                                }.get(outcome, outcome),
                                'odd': data['odd'],
                                'stake': stake,
                                'return': round(stake * data['odd'], 2),
                                'bookmaker': data['bookmaker']
                            })
                        
                        # Calcola totali
                        total_stake = sum(stakes.values())
                        guaranteed_return = min(d['return'] for d in details)
                        profit_value = round(guaranteed_return - total_stake, 2)
                        
                        surebets.append({
                            'sport': sport,
                            'event': event_name,
                            'market': market_type,
                            'profit': round(profit, 2),
                            'total_inversion': round(total_inversion, 4),
                            'details': details,
                            'bookmakers': list(set(d['bookmaker'] for d in details)),
                            'total_stake': total_stake,
                            'guaranteed_return': guaranteed_return,
                            'profit_value': profit_value,
                            'is_live': is_live
                        })
    
    return surebets

@app.route("/")
def index():
    """Endpoint principale che mostra tutte le surebet"""
    last_updated = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    all_surebets = []
    error = None
    
    for sport in CONFIG['SPORTS']:
        # Prematch
        prematch_data, prematch_error = get_odds(sport, is_live=False)
        if prematch_error:
            error = prematch_error
        elif prematch_data:
            all_surebets.extend(find_surebets(prematch_data, sport, False))
        
        # Live
        live_data, live_error = get_odds(sport, is_live=True)
        if live_error:
            error = live_error
        elif live_data:
            all_surebets.extend(find_surebets(live_data, sport, True))
    
    # Ordina per profitto decrescente
    all_surebets.sort(key=lambda x: x['profit'], reverse=True)
    
    return render_template_string(HTML_TEMPLATE,
        surebets=all_surebets,
        error=error,
        bookmakers=CONFIG['BOOKMAKERS'],
        min_profit=CONFIG['MIN_PROFIT'],
        last_updated=last_updated)

if __name__ == "__main__":
    print("""
   _____ _____ _____ _____ _____ _____ _____ 
  / ____|  __ \_   _|  __ \_   _/ ____|_   _|
 | (___ | |__) || | | |__) || || |      | |  
  \___ \|  ___/ | | |  _  / | || |      | |  
  ____) | |    _| |_| | \ \_| || |____ _| |_ 
 |_____/|_|   |_____|_|  \_\_____\_____|_____|
    """)
    print("\n🔍 Surebet Finder Pro - Calcio/Tennis/Basket")
    print(f"💰 Importo standard: €{CONFIG['STAKE']} | Profitto minimo: {CONFIG['MIN_PROFIT']}%")
    print(f"🏦 Bookmaker attivi: {', '.join(CONFIG['BOOKMAKERS'])}")
    print("\nAvvio server... http://localhost:5000")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))