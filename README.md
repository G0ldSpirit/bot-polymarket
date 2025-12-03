# Polymarket Trading Bot

Un bot de trading automatique pour les marchés prédictifs Polymarket.

## Fonctionnalités

- **Trading automatique** : Achat et vente automatique basés sur des stratégies configurables
- **Arbitrage BTC** : Stratégie spéciale pour le prix du Bitcoin (achète UP + DOWN)
- **Dashboard temps réel** : Interface terminal pour suivre positions, P&L, et trades
- **Multiples stratégies** :
  - **Momentum** : Trade basé sur les tendances de prix
  - **Arbitrage** : Détecte les opportunités d'arbitrage entre YES/NO
  - **Value** : Trading basé sur l'estimation de la valeur réelle
  - **BTC Arbitrage** : Arbitrage spécialisé sur les marchés BTC 1H
- **Gestion des risques** :
  - Stop Loss automatique
  - Take Profit automatique
  - Limite de positions ouvertes
- **Mode Dry Run** : Test sans risque (aucune transaction réelle)
- **Interface CLI** : Commandes simples pour contrôler le bot

## Installation

### Prérequis

- Python 3.9+
- Un wallet Ethereum avec des fonds sur Polygon
- USDC sur Polygon pour le trading

### Étapes

1. Cloner le repository :
```bash
git clone https://github.com/votre-repo/bot-polymarket.git
cd bot-polymarket
```

2. Créer un environnement virtuel :
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement :
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
```

## Configuration

Éditer le fichier `.env` avec vos paramètres :

```env
# Clé privée de votre wallet (SANS le préfixe 0x)
PRIVATE_KEY=votre_cle_privee_ici

# Paramètres de trading
MAX_TRADE_AMOUNT=100          # Maximum par trade en USDC
STOP_LOSS_PERCENTAGE=10       # Stop loss en %
TAKE_PROFIT_PERCENTAGE=20     # Take profit en %
MAX_OPEN_POSITIONS=5          # Nombre max de positions

# Mode test
DRY_RUN=true                  # true = pas de vraies transactions
```

**IMPORTANT** : Ne partagez JAMAIS votre clé privée !

## Utilisation

### Mode BTC Arbitrage (Recommandé pour débuter)

Le mode BTC arbitrage recherche les marchés de prédiction du prix du Bitcoin sur 1 heure et achète automatiquement les deux côtés (UP et DOWN) quand une opportunité d'arbitrage existe.

```bash
# Lancer le bot BTC avec dashboard
python main.py btc

# Options disponibles :
python main.py btc --min-spread 0.03    # Spread minimum de 3%
python main.py btc --amount 100          # 100 USDC par côté
python main.py btc --timeframe 4h        # Marchés 4 heures
python main.py btc --no-dashboard        # Sans interface graphique
```

**Comment ça marche :**
- Si UP coûte 0.45 et DOWN coûte 0.48 → Total = 0.93
- Le bot achète les deux pour 0.93
- À l'expiration, un des deux vaudra 1.00
- Profit garanti = 0.07 (7%)

### Démarrer le bot général

```bash
# Démarrer avec les stratégies par défaut (momentum + arbitrage)
python main.py start

# Démarrer avec des stratégies spécifiques
python main.py start --momentum --no-arbitrage

# Activer toutes les stratégies
python main.py start --momentum --arbitrage --value
```

### Dashboard en temps réel

```bash
# Afficher le dashboard sans lancer le bot
python main.py dashboard
```

Le dashboard affiche :
- Balance et P&L de session
- Statistiques de trading (trades, win rate, etc.)
- Positions ouvertes avec P&L en temps réel
- Historique des trades récents
- Info sur le marché BTC actuel

### Commandes disponibles

```bash
# Voir le statut et les positions
python main.py status

# Voir l'historique et les statistiques
python main.py history

# Lister les marchés disponibles
python main.py markets --limit 20

# Lister uniquement les marchés BTC
python main.py markets --btc

# Voir le carnet d'ordres d'un token
python main.py orderbook <TOKEN_ID>

# Acheter manuellement
python main.py buy <TOKEN_ID> <AMOUNT_USDC>
python main.py buy <TOKEN_ID> <AMOUNT_USDC> --price 0.50

# Vendre manuellement
python main.py sell <TOKEN_ID> <SIZE>
python main.py sell <TOKEN_ID> <SIZE> --price 0.60

# Annuler tous les ordres
python main.py cancel-all
```

## Stratégies

### BTC Arbitrage Strategy (Nouveau)
Stratégie spécialisée pour les marchés de prédiction du prix du Bitcoin :
- Recherche les marchés BTC 1H/4H/24H
- Achète simultanément UP et DOWN quand spread > seuil
- Profit garanti si total < 1

### Momentum Strategy
Analyse les mouvements de prix récents et génère des signaux basés sur le momentum :
- **Achat** : Momentum positif > seuil configuré
- **Vente** : Momentum négatif < seuil configuré

### Arbitrage Strategy
Recherche les opportunités d'arbitrage :
- Analyse si YES + NO < 1 (opportunité d'achat)
- Analyse si YES + NO > 1 (opportunité de vente)

### Value Strategy
Trading basé sur votre estimation de la probabilité réelle :
- Définissez une "fair value" pour les marchés que vous suivez
- Le bot achète quand le prix est en dessous de votre estimation
- Le bot vend quand le prix est au-dessus de votre estimation

## Structure du projet

```
bot-polymarket/
├── main.py                  # Point d'entrée CLI
├── requirements.txt         # Dépendances Python
├── .env.example             # Template de configuration
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py            # Gestion de la configuration
│   ├── client.py            # Client API Polymarket
│   ├── bot.py               # Logique principale du bot
│   ├── dashboard.py         # Interface dashboard temps réel
│   └── strategies/
│       ├── __init__.py
│       ├── base.py          # Classe de base des stratégies
│       ├── momentum.py      # Stratégie momentum
│       ├── arbitrage.py     # Stratégie arbitrage
│       ├── value.py         # Stratégie value
│       └── btc_arbitrage.py # Stratégie arbitrage BTC
├── logs/                    # Fichiers de log
└── data/                    # Données persistantes
```

## Exemple de Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│ Polymarket Trading Bot          Mode: DRY RUN      ● RUNNING   │
├─────────────────────────────────────────────────────────────────┤
│ 💰 Balance          │ 📈 Open Positions                        │
│ ─────────────────── │ ──────────────────────────────────────── │
│ Balance    $1000.00 │ Market     Entry   Current  P&L    P&L%  │
│ Session    +$12.50  │ BTC UP...  $0.450  $0.460   +$2   +2.2%  │
│ Total P&L  +$45.00  │ BTC DOWN.. $0.480  $0.475   -$1   -1.0%  │
│                     │                                          │
│ ₿ BTC 1H Market     │ 📜 Recent Trades                         │
│ ─────────────────── │ ──────────────────────────────────────── │
│ UP Price   $0.460   │ 14:32:01  BUY   BTC UP    $0.450  $50    │
│ DOWN Price $0.475   │ 14:32:02  BUY   BTC DOWN  $0.480  $50    │
│ Total      $0.935   │ 14:15:00  SELL  ETH YES   $0.620  +$8    │
│ Profit     +6.5%    │                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Avertissements

- **Risque financier** : Le trading comporte des risques. Vous pouvez perdre de l'argent.
- **Mode test** : Commencez TOUJOURS en mode `DRY_RUN=true` pour tester.
- **Petits montants** : Commencez avec de petits montants pour comprendre le fonctionnement.
- **Surveillance** : Surveillez régulièrement votre bot et vos positions.
- **Arbitrage** : Les opportunités d'arbitrage sont rares et compétitives.

## Développement

### Ajouter une nouvelle stratégie

1. Créer un fichier dans `src/strategies/`
2. Hériter de `BaseStrategy`
3. Implémenter la méthode `analyze()`
4. Ajouter l'import dans `src/strategies/__init__.py`

```python
from .base import BaseStrategy, TradeSignal, Signal

class MaStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MaStrategy")

    def analyze(self, market, orderbook) -> Optional[TradeSignal]:
        # Votre logique ici
        return None
```

## Licence

MIT License
