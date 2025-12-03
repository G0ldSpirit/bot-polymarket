# Polymarket Trading Bot

Un bot de trading automatique pour les marchés prédictifs Polymarket.

## Fonctionnalités

- **Trading automatique** : Achat et vente automatique basés sur des stratégies configurables
- **Multiples stratégies** :
  - **Momentum** : Trade basé sur les tendances de prix
  - **Arbitrage** : Détecte les opportunités d'arbitrage entre YES/NO
  - **Value** : Trading basé sur l'estimation de la valeur réelle
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

### Démarrer le bot

```bash
# Démarrer avec les stratégies par défaut (momentum + arbitrage)
python main.py start

# Démarrer avec des stratégies spécifiques
python main.py start --momentum --no-arbitrage

# Activer toutes les stratégies
python main.py start --momentum --arbitrage --value
```

### Commandes disponibles

```bash
# Voir le statut et les positions
python main.py status

# Lister les marchés disponibles
python main.py markets --limit 20

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
├── main.py              # Point d'entrée CLI
├── requirements.txt     # Dépendances Python
├── .env.example         # Template de configuration
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py        # Gestion de la configuration
│   ├── client.py        # Client API Polymarket
│   ├── bot.py           # Logique principale du bot
│   └── strategies/
│       ├── __init__.py
│       ├── base.py      # Classe de base des stratégies
│       ├── momentum.py  # Stratégie momentum
│       ├── arbitrage.py # Stratégie arbitrage
│       └── value.py     # Stratégie value
├── logs/                # Fichiers de log
└── data/                # Données persistantes
```

## Avertissements

- **Risque financier** : Le trading comporte des risques. Vous pouvez perdre de l'argent.
- **Mode test** : Commencez TOUJOURS en mode `DRY_RUN=true` pour tester.
- **Petits montants** : Commencez avec de petits montants pour comprendre le fonctionnement.
- **Surveillance** : Surveillez régulièrement votre bot et vos positions.

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
