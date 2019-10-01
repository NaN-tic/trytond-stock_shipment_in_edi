# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import shipment


def register():
    Pool.register(
        shipment.Cron,
        shipment.Move,
        shipment.ShipmentIn,
        shipment.StockConfiguration,
        module='stock_shipment_in_edi', type_='model')
