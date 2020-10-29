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


__all__ = ['Move', 'StockConfiguration', 'ShipmentIn', 'Cron']

DEFAULT_FILES_LOCATION = '/tmp/'
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = 'DESADV_ediversa.yml'
KNOWN_EXTENSIONS = ['.txt', '.edi', '.pla']


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.extend([
            ('stock.shipment.in|get_edi_shipments_cron',
            'Import EDI Shipment In Orders')])


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    edi_quantity = fields.Float('EDI Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states=MOVE_STATES, depends=['state', 'unit_digits'])
    edi_description = fields.Text('EDI Description', size=None)

    @classmethod
    def copy(cls, records, default=None):
        default = default.copy() if default else {}
        default.setdefault('edi_quantity')
        default.setdefault('edi_description')
        return super(Move, cls).copy(records, default=default)

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
        return lot


class ShipmentIn(EdifactMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def import_edi_input(cls, response, template):
        def get_new_move():
            move = None
            if product:
                move = Move()
                move.product = product
                move.on_change_product()
                move.quantity = quantity
                if values.get('unit'):
                    move.uom = values.get('unit')
                move.state = 'draft'
                move.company = purchase.company
                move.currency = purchase.currency
                move.planned_date = shipment.planned_date
                move.unit_price = product.list_price
                move.edi_description = values.get('description')
                move.shipment = shipment
                if (quantity or 0) >= 0:
                    move.from_location = purchase.party.supplier_location.id
                elif purchase.return_from_location:
                    move.from_location = purchase.return_from_location.id

                if (quantity or 0) >= 0:
                    if purchase.warehouse:
                        move.to_location = purchase.warehouse.input_location.id
                else:
                    move.to_location = purchase.party.supplier_location.id
            return move

        pool = Pool()
        ProductCode = pool.get('product.code')
        Template = pool.get('product.template')
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')

        total_errors = []
        control_chars = cls.set_control_chars(
            template.get('control_chars', {}))
        message = Message.from_str(response.upper().replace('\r', ''),
            characters=control_chars)
        segments_iterator = RewindIterator(message.segments)
        template_header = template.get('header', {})
        template_detail = template.get('detail', {})
        detail = [x for x in separate_section(segments_iterator, start='CPS')]
        del(segments_iterator)

        # If there isn't a segment DESADV_D_96A_UN_EAN005
        # means the file readed it's not a order response.
        if not message.get_segment('DESADV_D_96A_UN_EAN005'):
            return DO_NOTHING, NO_ERRORS
        rffs = message.get_segments('RFF')
        rff, = [x for x in rffs if x.elements[0] == 'ON'] or [None]
        template_rff = template_header.get('RFF')
        purchase, errors = cls._process_RFF(rff, template_rff, control_chars)
        if errors:
            total_errors += errors
        if not purchase:
            return None, total_errors

        shipment = cls()
        shipment.supplier = purchase.party
        shipment.on_change_supplier()
        shipment.warehouse = purchase.warehouse
        shipment.moves = purchase.pending_moves

        dtm = message.get_segment('DTM')
        template_dtm = template_header.get('DTM')
        effective_date, planned_date, errors = cls._process_DTM(dtm,
            template_dtm, control_chars)
        if errors:
            total_errors += errors
        shipment.effective_date = effective_date
        shipment.planned_date = planned_date

        bgm = message.get_segment('BGM')
        template_bgm = template_header.get('BGM')
        reference, errors = cls._process_BGM(bgm, template_bgm,
            control_chars)
        if errors:
            total_errors += errors
        shipment.reference = reference

        del(template_header)

        shipment.save()

        scannable_codes = ProductCode.search([
                ('product', 'in', shipment.scannable_products)
                ])
        scannable_products = {pc.number: pc.product for pc in scannable_codes}
        to_save = []
        for cps_group in detail:
            segments_iterator = RewindIterator(cps_group)
            linegroups = [x for x in separate_section(segments_iterator,
                start='LIN')]
            for linegroup in linegroups:
                values = {}
                for segment in linegroup:
                    if segment.tag not in list(template_detail.keys()):
                        continue
                    template_segment = template_detail.get(segment.tag)
                    tag = (segment.tag if segment.tag.endswith('LIN') else
                        '{}LIN'.format(segment.tag))
                    process = eval('cls._process_{}'.format(tag))
                    to_update, errors = process(segment, template_segment)
                    if errors:
                        # If there are errors the linegroup isn't processed
                        break
                    if to_update:
                        values.update(to_update)

                if errors:
                    total_errors += errors
                    continue

                product = scannable_products.get(values.get('product'))
                quantity = values.get('quantity')
                if not quantity:
                    continue
                matching_moves = None
                if product:
                    matching_moves = [m for m in shipment.pending_moves if
                        (m.product == product) and (m.pending_quantity > 0)]
                    if matching_moves:
                        move = matching_moves[0]
                    else:
                        move = get_new_move()
                else:
                    product_code, = ProductCode.search([
                            ('number', '=', values.get('product'))
                            ], limit=1) or [None]
                    if not product_code:
                        continue
                    product = product_code.product
                    move = get_new_move()
                move.edi_quantity = quantity
                move.edi_description = values.get('description')
                if hasattr(Template, 'lot_required') and product.lot_required:
                    expiration = None
                    if hasattr(Template, 'expiration_state'):
                        expiration = product.expiration_state
                    lots = Lot.search([
                            ('number', '=', values.get('lot')),
                            ('product', '=', move.product)
                            ], limit=1)
                    if lots:
                        lot, = lots
                        if ((not expiration or expiration != 'none')
                                and values.get('expiration_date', False)):
                            expiration_date = values.get('expiration_date')
                            if expiration_date and lot.expiration_date:
                                if expiration_date < lot.expiration_date:
                                    lot.expiration_date = expiration_date
                    else:
                        lot = move._get_new_lot(values, expiration)
                    if lot:
                        lot.save()
                        move.lot = lot
                to_save.append(move)

        if to_save:
            Move.save(to_save)

        return shipment, total_errors

    @classmethod
    @with_segment_check
    def _process_RFF(cls, segment, template_segment, control_chars=None):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        purchase_num = segment.elements[1]
        purchase, = Purchase.search([
                ('number', '=', purchase_num),
                ('state', 'in', ('processing', 'done'))
                ], limit=1) or [None]
        if not purchase:
            purchases = Purchase.search([
                    ('reference', '=', purchase_num),
                    ('state', 'in', ('processing', 'done'))
                    ])
            if len(purchases) == 1:
                purchase = purchase[0]
        if not purchase:
            error_msg = 'Purchase number {} not found'.format(purchase_num)
            serialized_segment = Serializer(control_chars).serialize([segment])
            return DO_NOTHING, ['{}: {}'.format(error_msg, serialized_segment)]
        return purchase, NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_DTM(cls, segment, template, control_chars=None):
        effective_date = cls.get_datetime_obj_from_edi_date(
            segment.elements[0])
        planned_date = (cls.get_datetime_obj_from_edi_date(
            segment.elements[1]) if len(segment.elements) > 1 else None)
        return effective_date, planned_date, NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_BGM(cls, segment, template, control_chars=None):
        return segment.elements[0], NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_LIN(cls, segment, template):
        return {'product': segment.elements[0]}, NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_QTYLIN(cls, segment, template):
        pool = Pool()
        Uom = pool.get('product.uom')
        result = {}
        qualifier = segment.elements[0]
        if qualifier != '12':
            return DO_NOTHING, NO_ERRORS
        if len(segment.elements) > 2:
            uom_value = UOMS_EDI_TO_TRYTON.get(segment.elements[2], 'u')
        else:
            uom_value = 'u'
        uom, = Uom.search([('symbol', '=', uom_value)], limit=1)
        result['unit'] = uom
        quantity = float(segment.elements[1])
        result['quantity'] = quantity
        return result, NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_IMDLIN(cls, segment, template):
        description = segment.elements[1] or None
        return {'description': description}, NO_ERRORS

    @classmethod
    @with_segment_check
    def _process_PCILIN(cls, segment, template):
        elements_lenght = len(segment.elements)
        expiration_date = (cls.get_datetime_obj_from_edi_date(
                segment.elements[1]) if elements_lenght > 1 else None)
        lot = segment.elements[7] if elements_lenght > 6 else None
        result = {
            'expiration_date': (expiration_date.date() if expiration_date
                else None),
            'lot': lot
            }
        return result, NO_ERRORS

    @classmethod
    def _process_CPSLIN(cls, segment, template):
        return DO_NOTHING, NO_ERRORS

    @classmethod
    def create_edi_shipments(cls):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        source_path = os.path.abspath(configuration.inbox_path_edi or
            DEFAULT_FILES_LOCATION)
        errors_path = os.path.abspath(configuration.errors_path_edi
            or DEFAULT_FILES_LOCATION)
        template_name = (configuration.template_order_response_edi
            or DEFAULT_TEMPLATE)
        template_path = os.path.join(os.path.join(MODULE_PATH, 'templates'),
            template_name)
        template = EdiTemplate(template_name, template_path)
        return cls.process_edi_inputs(source_path, errors_path, template)

    @classmethod
    def get_edi_shipments_cron(cls):
        cls.create_edi_shipments()
        return True


class StockConfiguration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    inbox_path_edi = fields.Char('Inbox Path EDI')
    errors_path_edi = fields.Char('Errors Path')
    template_order_response_edi = fields.Char('Template EDI Used for Response')
