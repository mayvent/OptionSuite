import unittest
import datetime
import decimal
import json
from portfolioManager import portfolio
from optionPrimitives import optionPrimitive, strangle
from base import put
from base import call
from events import signalEvent, tickEvent
from riskManagement import strangleRiskManagement

class TestPortfolio(unittest.TestCase):

  def setUp(self):
    """Create portfolio object to be shared among tests."""

    # Strangle object to be shared among tests.
    putOpt = put.Put(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2786.24),
                     strikePrice=decimal.Decimal(2690), delta=-0.16, gamma=0.01, theta=0.02, vega=0.03,
                     dateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                     expirationDateTime=datetime.datetime.strptime('01/20/2021', "%m/%d/%Y"),
                     bidPrice=decimal.Decimal(7.45), askPrice=decimal.Decimal(7.50), tradePrice=decimal.Decimal(7.475))
    callOpt = call.Call(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2786.24),
                        strikePrice=decimal.Decimal(2855), delta=0.16, gamma=0.01, theta=0.02, vega=0.03,
                        dateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                        expirationDateTime=datetime.datetime.strptime('01/20/2021', "%m/%d/%Y"),
                        bidPrice=decimal.Decimal(5.20), askPrice=decimal.Decimal(5.40),
                        tradePrice=decimal.Decimal(5.30))
    self.strangleObj = strangle.Strangle(orderQuantity=1, callOpt=callOpt, putOpt=putOpt,
                                         buyOrSell=optionPrimitive.TransactionType.SELL)
    self.riskManagement = strangleRiskManagement.StrangleRiskManagement(
      strangleRiskManagement.StrangleManagementStrategyTypes.HOLD_TO_EXPIRATION)

    # Load the JSON config for calculating commissions and fees. Test with Tastyworks as the brokerage.
    self.pricingSourceConfigFile = './dataHandler/pricingConfig.json'
    self.pricingSource = 'tastyworks'

    startingCapital = decimal.Decimal(1000000)
    maxCapitalToUse = 0.5
    maxCapitalToUsePerTrade = 0.5
    self.portfolioObj = portfolio.Portfolio(startingCapital, maxCapitalToUse, maxCapitalToUsePerTrade,
                                            pricingSource=self.pricingSource,
                                            pricingSourceConfigFile=self.pricingSourceConfigFile)

  def testOnSignalSucess(self):
    """Tests that onSignal event successfully updates portfolio."""
    # Create signal event.
    event = signalEvent.SignalEvent()
    event.createEvent([self.strangleObj, self.riskManagement])

    # Test portfolio onSignal event.
    self.portfolioObj.onSignal(event)

    # Check that positions array in portfolio is not empty.
    self.assertNotEqual(len(self.portfolioObj.activePositions), 0)

    # Check that the buying power used by the strangle is correct.
    self.assertAlmostEqual(self.portfolioObj.totalBuyingPower, decimal.Decimal(63311.5427))

    # Get the total delta value of the portfolio and check that it is 0.01.
    self.assertAlmostEqual(self.portfolioObj.totalDelta, 0.0)

  def testOnSignalNotEnoughBuyingPower(self):
    """Tests that total buying power is not updated if there's not enough buying power."""
    startingCapital = decimal.Decimal(100000)
    maxCapitalToUse = 0.1
    maxCapitalToUsePerTrade = 0.1
    portfolioObj = portfolio.Portfolio(startingCapital, maxCapitalToUse, maxCapitalToUsePerTrade,
                                       pricingSource=self.pricingSource,
                                       pricingSourceConfigFile=self.pricingSourceConfigFile)

    event = signalEvent.SignalEvent()
    event.createEvent([self.strangleObj, self.riskManagement])
    portfolioObj.onSignal(event)

  def testUpdatePortfolio(self):
    """Tests the ability to update option values for a position in the portfolio."""
    # Create strangle event.
    event = signalEvent.SignalEvent()
    event.createEvent([self.strangleObj, self.riskManagement])

    # Create portfolio onSignal event, which adds the position to the portfolio.
    startingCapital = decimal.Decimal(1000000)
    maxCapitalToUse = 0.5
    maxCapitalToUsePerTrade = 0.5
    portfolioObj = portfolio.Portfolio(startingCapital, maxCapitalToUse, maxCapitalToUsePerTrade,
                                       pricingSource=self.pricingSource,
                                       pricingSourceConfigFile=self.pricingSourceConfigFile)
    portfolioObj.onSignal(event)

    # Next, create a strangle with the next days prices and update the portfolio values.
    putOpt = put.Put(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2786.24),
                     strikePrice=decimal.Decimal(2690), delta=-0.16, gamma=0.01, theta=0.02, vega=0.03,
                     dateTime=datetime.datetime.strptime('01/02/2021', "%m/%d/%Y"),
                     expirationDateTime=datetime.datetime.strptime('01/20/2021', "%m/%d/%Y"),
                     bidPrice=decimal.Decimal(6.45), askPrice=decimal.Decimal(6.50), tradePrice=decimal.Decimal(6.475))
    callOpt = call.Call(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2786.24),
                        strikePrice=decimal.Decimal(2855), delta=0.16, gamma=0.01, theta=0.02, vega=0.03,
                        dateTime=datetime.datetime.strptime('01/02/2021', "%m/%d/%Y"),
                        expirationDateTime=datetime.datetime.strptime('01/20/2021', "%m/%d/%Y"),
                        bidPrice=decimal.Decimal(4.20), askPrice=decimal.Decimal(4.40),
                        tradePrice=decimal.Decimal(4.30))

    # Create tick event and update portfolio values.
    testOptionChain = [callOpt, putOpt]
    event = tickEvent.TickEvent()
    event.createEvent(testOptionChain)
    portfolioObj.updatePortfolio(event)

    # Check that the new portfolio values are correct (e.g., buying power, total delta, total gamma, etc).
    self.assertAlmostEqual(portfolioObj.totalBuyingPower, decimal.Decimal(63210.0))
    self.assertAlmostEqual(portfolioObj.totalVega, 0.06)
    self.assertAlmostEqual(portfolioObj.totalDelta, 0.0)
    self.assertAlmostEqual(portfolioObj.totalGamma, 0.02)
    self.assertAlmostEqual(portfolioObj.totalTheta, 0.04)
    self.assertAlmostEqual(portfolioObj.netLiquidity, decimal.Decimal(1000198.4573))

  def testUpdatePortfolioRiskManagementHoldToExpiration(self):
    """Tests that the position is removed from the portfolio when expiration occurs."""
    # Create a new position in addition to the default self.strangleObj position.
    startingCapital = decimal.Decimal(1000000)
    maxCapitalToUse = 0.5
    maxCapitalToUsePerTrade = 0.25
    portfolioObj = portfolio.Portfolio(startingCapital, maxCapitalToUse, maxCapitalToUsePerTrade,
                                       pricingSource=self.pricingSource,
                                       pricingSourceConfigFile=self.pricingSourceConfigFile)

    # Add first position to the portfolio
    event = signalEvent.SignalEvent()
    event.createEvent([self.strangleObj, self.riskManagement])
    portfolioObj.onSignal(event)

    putOpt = put.Put(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2800.00),
                     strikePrice=decimal.Decimal(2700), delta=-0.16, gamma=0.01, theta=0.02, vega=0.03,
                     dateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                     expirationDateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                     bidPrice=decimal.Decimal(8.00), askPrice=decimal.Decimal(8.50), tradePrice=decimal.Decimal(8.25))
    callOpt = call.Call(underlyingTicker='SPX', underlyingPrice=decimal.Decimal(2800.00),
                        strikePrice=decimal.Decimal(3000), delta=0.16, gamma=0.01, theta=0.02, vega=0.03,
                        dateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                        expirationDateTime=datetime.datetime.strptime('01/01/2021', "%m/%d/%Y"),
                        bidPrice=decimal.Decimal(6.00), askPrice=decimal.Decimal(6.50),
                        tradePrice=decimal.Decimal(6.25))
    strangleObj = strangle.Strangle(orderQuantity=1, callOpt=callOpt, putOpt=putOpt,
                                    buyOrSell=optionPrimitive.TransactionType.SELL)

    # Add second position to the portfolio.
    event = signalEvent.SignalEvent()
    event.createEvent([strangleObj, self.riskManagement])
    portfolioObj.onSignal(event)

    # Update the portfolio, which should remove the second event. We do not change the prices of the putOpt or callOpt.
    testOptionChain = [callOpt, putOpt]
    event = tickEvent.TickEvent()
    event.createEvent(testOptionChain)
    portfolioObj.updatePortfolio(event)
    # Only one position should be left in the portfolio after removing the expired position.
    self.assertEqual(len(portfolioObj.activePositions), 1)


if __name__ == '__main__':
    unittest.main()
