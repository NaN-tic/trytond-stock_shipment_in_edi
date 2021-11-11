# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import edi_shipment
from . import shipment


def register():
    Pool.register(
        edi_shipment.Cron,
        edi_shipment.SupplierEdi,
        edi_shipment.EdiShipmentReference,
        edi_shipment.EdiShipmentInLine,
        edi_shipment.EdiShipmentIn,
        edi_shipment.EdiShipmentInLineQty,
        edi_shipment.StockConfiguration,
        shipment.ShipmentIn,
        module='stock_shipment_in_edi', type_='model')
