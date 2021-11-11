# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _is_needed_to_create_lot(self, moves=None):
        for move in moves:
            if move.product == self.scanned_product and move.lot:
                return False
        return super()._is_needed_to_create_lot(moves)
