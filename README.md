# cyrpto_trader

Trading automation on poloniex cryptocoin exchange

Using poloniex api python library from https://github.com/Aula13/poloniex


To install dependencies use python pip command

```
pip install -r requiremenets.txt
```

# Usage

To sell coins use this:

```
python cyripto_trader.py sell_all
```

To buy coins with all your BTC balance use this:

```
python cyripto_trader.py buy_all
```

To use the basic ping-pong scalping strategy (highly risky!):

```
python cyripto_trader.py scalp
```

_**Disclaimer:** This is highly experimental software. Use it at your own risk._
_This may make you lose all you money, scare your cat and make your dog piss on the carpet._

# Docker instructions

No previous installation (`python` or whatsoever) is required other than `docker`.

 Build the docker image (once):

 ```
 docker build -t crypto_traders .
 ```

Run the image
```
docker run crypto_traders
```

# Donation

You can send me some small amount of BTC if you like. 
I may use it to test this better or I'll buy some beers. :)

**BTC :** 1AtiEpW9X97Z4RupdPVqnxGvc5pmAbCVTz
