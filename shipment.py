# encoding: utf-8
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
import os
from trytond.modules.stock.move import STATES as MOVE_STATES
from trytond.modules.edocument_unedifact.edocument import (EdifactMixin,
    UOMS_EDI_TO_TRYTON, EdiTemplate)
from edifact.message import Message
from edifact.serializer import Serializer
from edifact.utils import (with_segment_check, validate_segment,
    separate_section, RewindIterator, DO_NOTHING, NO_ERRORS)
from datetime import datetime
import logging

logger = logging.getLogger('stock_shipment_in_edi')

DEFAULT_FILES_LOCATION = '/tmp/'
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = 'DESADV_ediversa.yml'
KNOWN_EXTENSIONS = ['.txt', '.edi', '.pla']


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _get_new_lot(self, values, expiration):
        pool = Pool()
        Lot = pool.get('stock.lot')

        today = datetime.today().date()
        lot = Lot()
        lot.number = values.get('lot') or today.isoformat()
        lot.product = self.product
        if ((not expiration or expiration != 'none')
                and values.get('expiration_date', False)):
            lot.expiration_date = values.get('expiration_date')
        else:
            lot.on_change_product()
        return lot
