#!/usr/bin/env python
# -*- coding: utf-8 -*-
import decimal
import datetime
import time

import argparse

from poloniex import Poloniex

# api keys are in the settings.yaml
try:
    import yaml
    with open('settings.yaml') as f:
        settings = yaml.safe_load(f)
        if not (settings and
                settings.get('polo_api', None) and
                settings['polo_api'].get('key', None) and
                settings['polo_api'].get('secret', None)):
            raise ValueError('api keys missing')

except (ValueError, IOError):
    print "settings not found."
    print "create a file named settings.yaml and put them here like this:"
    print "polo_api:"
    print "  key: super_rich_acounts_api_key"
    print "  secret: super_secret_top_secret"
    print ""
    exit()

class Trader(object):
    """Trader class
    """
    def __init__(self, api_key, api_secret, coin, currency, dust_total=10,
                 dust_amount=100.0, min_spread=0.0001, max_trading_amount=1):
        # set currency pair
        self.coin = coin
        self.currency = currency
        self.my_pair = '%s_%s' % (currency, coin)

        # we'll need this while finding buy/sell prices
        self.dust_total = self.make_satoshi(dust_total)
        self.dust_amount = self.make_satoshi(dust_amount)
        self.min_spread = self.make_satoshi(min_spread)
        self.max_trading_amount = self.make_satoshi(max_trading_amount)

        # initialize the poloniex api
        self.api_key = api_key
        self.api_secret = api_secret
        self.polo = Poloniex(api_key, api_secret)

        # initialize other variables
        self.coin_balance = self.make_satoshi('0.0')
        self.currency_balance = self.make_satoshi('0.0')
        self.total_coin_balance = self.make_satoshi('0.0')
        self.total_currency_balance = self.make_satoshi('0.0')

        self.open_orders_raw = []
        self.open_orders = []
        self.open_orders_sell = []
        self.open_orders_buy = []

        self.order_book_raw = []
        self.order_book = {}
        self.order_book["buy"] = []
        self.order_book["sell"] = []

        self.sell_price = self.make_satoshi('0.0')
        self.buy_price = self.make_satoshi('0.0')
        self.price_spread = self.make_satoshi('0.0')
        self.sell_amount = self.make_satoshi('0.0')
        self.buy_amount = self.make_satoshi('0.0')
        self.trade = False

        # those are hardcoded. may be added to settings later.
        self.min_currency_balance = self.make_satoshi('0.00100000')
        # seconds to wait for exchange rate limits.
        self.exchange_wait_time = 0.8


    def make_satoshi(self, num):
        return decimal.Decimal(num).quantize(decimal.Decimal('1.00000000'))


    def load_open_orders(self):
        """
        loads open orders. Resets the balances so load_balances method should be called after.
        """
        self.total_coin_balance = self.make_satoshi('0.0')
        self.total_currency_balance = self.make_satoshi('0.0')
        self.open_orders_raw = self.polo.returnOpenOrders(currencyPair=self.my_pair)
        self.open_orders = []
        self.open_orders_sell = []
        self.open_orders_buy = []
        for item in self.open_orders_raw:
            order = {}
            order['type'] = item['type']
            order["order_number"] = item['orderNumber']
            order["price"] = self.make_satoshi(item['rate'])
            order["amount"] = self.make_satoshi(item['amount'])
            order["total"] = self.make_satoshi(order['price'] * order['amount'])
            order["starting_amount"] = self.make_satoshi(item['startingAmount'])

            self.open_orders.append(order)
            if order['type'] == 'sell':
                self.open_orders_sell.append(order)
                self.total_coin_balance = self.total_coin_balance + order["amount"]
            else:
                self.open_orders_buy.append(order)
                self.total_currency_balance = self.total_currency_balance + order["total"]

        return self.open_orders


    def load_balances(self):
        # first load the open orders to get the balances in open orders.
        self.load_open_orders()
        # request from exchange
        self.balances = self.polo.returnBalances()
        # set the coin balance
        self.coin_balance = self.make_satoshi(self.balances[self.coin])
        self.total_coin_balance = self.total_coin_balance + self.coin_balance
        # '0.00000001' makes things complicated. get rid of it.
        if self.coin_balance <= self.make_satoshi('0.00000001'):
            self.coin_balance = self.make_satoshi('0.0')
        if self.total_coin_balance <= self.make_satoshi('0.00000001'):
            self.total_coin_balance = self.make_satoshi('0.0')
        # set the main currency balance
        self.currency_balance = self.make_satoshi(self.balances[self.currency])
        self.total_currency_balance = self.total_currency_balance + self.currency_balance
        # '0.00000001' makes things complicated. get rid of it.
        if self.currency_balance <= self.make_satoshi('0.00000001'):
            self.currency_balance = self.make_satoshi('0.0')
        if self.total_currency_balance <= self.make_satoshi('0.00000001'):
            self.total_currency_balance = self.make_satoshi('0.0')
        # added for debugging. make the BTC amount > 0 so we can test buying.
        # self.total_currency_balance = self.make_satoshi('0.10000000')


    def load_order_book(self):
        self.order_book_raw = self.polo.returnOrderBook(currencyPair=self.my_pair, depth='200')
        self.order_book["buy"] = []
        self.order_book["sell"] = []
        self.process_order_book('buy', self.order_book_raw["bids"])
        self.process_order_book('sell', self.order_book_raw["asks"])
        return self.order_book


    def process_order_book(self, order_type, order_book_raw):
        self.order_book[order_type] = []
        total = self.make_satoshi("0.0")
        for item in order_book_raw:
            order = {}
            order['type'] = order_type
            order["price"] = self.make_satoshi(item[0])
            order["amount"] = self.make_satoshi(item[1])
            order["cur"] = self.make_satoshi(order["price"] * order["amount"])
            total = self.make_satoshi(total + order["cur"])
            order["total"] = total
            # mark the order if its my order. put order number from open_orders
            order['order_number'] = None
            for open_order in self.open_orders:
                if (open_order['type'] == order['type']) and (open_order["price"] == order["price"]):
                    order["order_number"] = open_order['order_number']
                    print "order:", order

            self.order_book[order_type].append(order)

        return self.order_book[order_type]


    def find_sell_price(self):
        total = self.make_satoshi("0.0")
        for order in self.order_book['sell']:
            if order['order_number'] is None:
                total = self.make_satoshi(total + order["cur"])
                if (order["amount"] >= DUST_AMOUNT) or (total >= DUST_TOTAL):
                    return self.make_satoshi(order["price"] - self.make_satoshi("0.00000003"))

        return False


    def find_buy_price(self):
        total = self.make_satoshi("0.0")
        for order in self.order_book['buy']:
            if order['order_number'] is None:
                total = self.make_satoshi(total + order["cur"])
                if (order["amount"] >= DUST_AMOUNT) or (total >= DUST_TOTAL):
                    return self.make_satoshi(order["price"] + self.make_satoshi("0.00000003"))

        return False


    def decide_to_trade(self):
        self.sell_price = self.find_sell_price()
        self.buy_price = self.find_buy_price()
        self.price_spread = self.sell_price - self.buy_price

        print "Sell Price:", self.sell_price
        print "Buy Price:", self.buy_price
        print "Price Spread:", self.price_spread


        if (not self.sell_price) or (not self.buy_price):
            print "Something is wrong with sell and buy prices. Will not trade!"
            self.trade = False
            return False


        if self.total_currency_balance > self.min_currency_balance:
            print 'I have %s %s, will try to buy %s.' % (
                self.total_currency_balance, self.currency, self.coin)
            self.trade = 'buy'
            return True
        else:
            if self.price_spread >= self.min_spread:
                print 'Spread is good. Will trade'
                # sell or buy?
                if self.total_coin_balance > 0:
                    print 'I have %s %s, will try to sell %s for %s.' % (
                        self.total_coin_balance, self.coin, self.coin,
                        self.currency)
                    self.trade = 'sell'
                    return True
                else:
                    print 'I have nothing to trade.'
                    self.trade = False
            else:
                print 'Price Spread is not good. Stop trading.'
                self.trade = False

        return False


    def cancel_open_orders(self, buy_sell):
        for order in self.open_orders:
            if order['type'] == buy_sell:
                print "canceling order:", order
                try:
                    retval = self.polo.cancelOrder(order["order_number"])
                except RuntimeError:
                    retval = False
                    print 'ERROR canceling order.'
                print "cancel order retval:", retval
                self.open_orders.remove(order)
                if buy_sell == 'sell':
                    self.open_orders_sell.remove(order)
                else:
                    self.open_orders_buy.remove(order)


    def cancel_open_order(self, order):
        print "canceling order:", order
        try:
            retval = self.polo.cancelOrder(order["order_number"])
        except RuntimeError:
            retval = False
            print 'ERROR canceling order.'
        time.sleep(0.2)
        print "cancel order retval:", retval
        self.open_orders.remove(order)
        if order['type'] == 'sell':
            self.open_orders_sell.remove(order)
        else:
            self.open_orders_buy.remove(order)


    def add_sell_order(self):
        # compute the amount
        if self.total_coin_balance > self.max_trading_amount:
            self.sell_amount = self.max_trading_amount
        else:
            self.sell_amount = self.total_coin_balance

        print "self.sell_amount:", self.sell_amount
        # send order to exchange
        try:
            retval = self.polo.sell(currencyPair=self.my_pair, rate=self.sell_price, amount=self.sell_amount)
        except RuntimeError:
            print 'ERROR adding SELL order.'
            retval = False

        print retval

        return retval


    def sell(self):
        # cancel all buy orders first.
        self.cancel_open_orders('buy')
        # check open sell orders if the sell price is ok.
        for order in self.open_orders_sell:
            if order['price'] == self.sell_price:
                print "order is ok:", order
            else:
                # cancel the order.
                retval = self.cancel_open_order(order)

        print 'self.open_orders_sell:', len(self.open_orders_sell)
        if len(self.open_orders_sell) == 0:
            print 'adding a new sell order'
            retval = self.add_sell_order()


    def add_buy_order(self):
        # compute the amount
        if self.total_currency_balance > self.make_satoshi('0.00001000'):
            self.buy_amount = self.make_satoshi(self.total_currency_balance / self.buy_price) - self.make_satoshi('0.00000001')
            print "Buying amount:", self.buy_amount
        else:
            print "Buying amount is low. not buying:"
            return False

        # send order to exchange
        try:
            retval = self.polo.buy(currencyPair=self.my_pair, rate=self.buy_price, amount=self.buy_amount)
        except RuntimeError:
            print 'ERROR adding BUY order.'
            retval = False

        print retval

        return retval


    def buy(self):
        # cancel all buy orders first.
        self.cancel_open_orders('sell')
        # check open sell orders if the sell price is ok.
        for order in self.open_orders_buy:
            if order['price'] == self.buy_price:
                print "order is ok:", order
            else:
                # cancel the order.
                retval = self.cancel_open_order(order)

        print 'self.open_orders_buy:', len(self.open_orders_buy)
        if len(self.open_orders_buy) == 0:
            print 'adding a new buy order'
            retval = self.add_buy_order()


    def run_scalping(self):
        while True:
            now = datetime.datetime.now()
            print str(now)

            self.load_balances()
            self.load_order_book()

            print '%s Balance: %s' % (self.currency, self.total_currency_balance)
            print '%s Balance: %s' % (self.coin, self.total_coin_balance)

            # trade or not trade?
            trade = self.decide_to_trade()

            print "Trade?", trade

            if self.trade == 'sell':
                self.sell()
            elif self.trade == 'buy':
                self.buy()
            else:
                #Will not trade. Cancel all orders.
                self.cancel_open_orders('buy')
                self.cancel_open_orders('sell')

            print "."
            print "open orders:", self.open_orders
            print "."
            now = datetime.datetime.now()
            print str(now)

            print "Will wait a little bit for not to flood the exchange..."
            time.sleep(self.exchange_wait_time)


    def add_sell_all_order(self):
        # compute the amount
        self.sell_amount = self.total_coin_balance

        print "self.sell_amount:", self.sell_amount
        if self.sell_amount:
            # send order to exchange
            try:
                retval = self.polo.sell(currencyPair=self.my_pair,
                                        rate=self.sell_price,
                                        amount=self.sell_amount)
            except RuntimeError:
                print 'ERROR adding SELL ALL order.'
                retval = False

            print retval

            return retval
        else:
            return False


    def sell_all(self):
        # cancel all buy orders first.
        self.cancel_open_orders('buy')
        # check open sell orders if the sell price is ok.
        for order in self.open_orders_sell:
            if order['price'] == self.sell_price:
                print "order is ok:", order
            else:
                # cancel the order.
                retval = self.cancel_open_order(order)

        print 'self.open_orders_sell:', len(self.open_orders_sell)
        if len(self.open_orders_sell) == 0:
            print 'adding a new sell all order'
            retval = self.add_sell_all_order()


    def run_sell_all(self):
        self.trade = 'sell'
        while self.trade == 'sell':
            now = datetime.datetime.now()
            print str(now)

            self.load_balances()
            self.load_order_book()

            print '%s Balance: %s' % (self.currency, self.total_currency_balance)
            print '%s Balance: %s' % (self.coin, self.total_coin_balance)

            self.sell_price = self.find_sell_price()
            print "Sell Price:", self.sell_price

            if self.total_coin_balance > 0.0:
                print 'I have %s %s, will try to sell %s for %s.' % (
                    self.total_coin_balance, self.coin, self.coin,
                    self.currency)
                self.trade = 'sell'
            else:
                print 'I have nothing to trade.'
                self.trade = False

            if self.trade == 'sell':
                self.sell_all()
            else:
                #Will not trade. Cancel all orders.
                self.cancel_open_orders('buy')
                self.cancel_open_orders('sell')

            print "."
            print "open orders:", self.open_orders
            print "."
            now = datetime.datetime.now()
            print str(now)

            print "Will wait a little bit for not to flood the exchange..."
            time.sleep(self.exchange_wait_time)


    def add_buy_all_order(self):
        # compute the amount
        if self.total_currency_balance > self.make_satoshi('0.00001000'):
            top = self.total_currency_balance / self.buy_price
            self.buy_amount = self.make_satoshi(top) - self.make_satoshi('0.00000001')
            print "Buying amount:", self.buy_amount
        else:
            print "Buying amount is low. not buying:"
            return False

        # send order to exchange
        try:
            retval = self.polo.buy(currencyPair=self.my_pair, rate=self.buy_price, amount=self.buy_amount)
        except:
            print 'ERROR adding BUY ALL order.'
            retval = False

        print retval

        return retval


    def buy_all(self):
        # cancel all buy orders first.
        self.cancel_open_orders('sell')
        # check open sell orders if the sell price is ok.
        for order in self.open_orders_buy:
            if order['price'] == self.buy_price:
                print "order is ok:", order
            else:
                # cancel the order.
                retval = self.cancel_open_order(order)

        print 'self.open_orders_buy:', len(self.open_orders_buy)
        if len(self.open_orders_buy) == 0:
            print 'adding a new buy all order'
            retval = self.add_buy_all_order()


    def run_buy_all(self):
        self.trade = 'buy'
        while self.trade == 'buy':
            now = datetime.datetime.now()
            print str(now)

            self.load_balances()
            self.load_order_book()

            print '%s Balance: %s' % (self.currency, self.total_currency_balance)
            print '%s Balance: %s' % (self.coin, self.total_coin_balance)

            self.buy_price = self.find_buy_price()
            print "Buy Price:", self.buy_price

            if self.total_currency_balance > self.min_currency_balance:
                print 'I have %s %s, will try to buy %s.' % (self.total_currency_balance, self.currency, self.coin)
                self.trade = 'buy'
            else:
                print 'I have nothing to trade.'
                self.trade = False

            if self.trade == 'buy':
                self.buy_all()
            else:
                #Will not trade. Cancel all orders.
                self.cancel_open_orders('buy')
                self.cancel_open_orders('sell')

            print "."
            print "open orders:", self.open_orders
            print "."
            now = datetime.datetime.now()
            print str(now)

            print "Will wait a little bit for not to flood the exchange..."
            time.sleep(self.exchange_wait_time)


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument(
        'action',
        choices=['sell_all', 'buy_all', 'scalp'],
        help="What to do? sell_all, buy_all or scalp",
        )

    ARGS = PARSER.parse_args()
    ACTION = ARGS.action

    POLO_API_KEY = settings['polo_api']['key']
    POLO_API_SECRET = settings['polo_api']['secret']
    TRACE_CURRENCY = settings['coin']['my_coin']
    RETURN_CURRENCY = settings['coin']['currency']
    DUST_TOTAL = settings['dust_total']
    DUST_AMOUNT = settings['dust_amount']
    MIN_SPREAD = settings['min_spread']
    MAX_TRADING_AMOUNT = settings['max_trading_amount']

    TRADER = Trader(POLO_API_KEY, POLO_API_SECRET, TRACE_CURRENCY, RETURN_CURRENCY,
                    DUST_TOTAL, DUST_AMOUNT, MIN_SPREAD, MAX_TRADING_AMOUNT)

    if ACTION == "scalp":
        TRADER.run_scalping()
    elif ACTION == "sell_all":
        TRADER.run_sell_all()
    elif ACTION == "buy_all":
        TRADER.run_buy_all()
