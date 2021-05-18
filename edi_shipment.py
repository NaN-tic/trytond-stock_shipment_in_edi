# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
import os
from trytond.modules.account_invoice_edi.invoice import (SupplierEdiMixin,
    SUPPLIER_TYPE)
from datetime import datetime
from decimal import Decimal
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.pyson import Eval, Bool
import barcodenumber

DEFAULT_FILES_LOCATION = '/tmp/'
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
KNOWN_EXTENSIONS = ['.txt', '.edi', '.pla']
DATE_FORMAT = '%Y%m%d'


def to_date(value):
    if value is None or value == '':
        return None
    if len(value) > 8:
        value = value[0:8]
    if value == '00000000':
        return
    return datetime.strptime(value, DATE_FORMAT)


def to_decimal(value, digits=2):
    if value is None or value == '':
        return None
    return Decimal(value).quantize(Decimal('10')**-digits)


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.extend([
            ('edi.shipment.in|import_shipment_in',
            'Import EDI Shipment In Orders')])


class StockConfiguration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    inbox_path_edi = fields.Char('Inbox Path EDI')


class SupplierEdi(SupplierEdiMixin, ModelSQL, ModelView):
    'Supplier Edi'
    __name__ = 'edi.shipment.supplier'

    edi_shipment = fields.Many2One('edi.shipment.in', 'Edi Shipment')


class EdiShipmentReference(ModelSQL, ModelView):
    'Shipment In Reference'
    __name__ = 'edi.shipment.in.reference'

    # RFF, RFFLIN
    type_ = fields.Selection([
        (None, ''),
        ('DQ', 'Shipment'),
        ('ON', 'Purchase'),
        ('LI', 'Line Number'),
        ('VN', 'VN')],
        'Reference Code')
    reference = fields.Char('Reference')
    reference_date = fields.Date('Reference Date', readonly=True)
    origin = fields.Reference('Reference', selection='get_resource')
    edi_shipment_in_line = fields.Many2One('edi.shipment.in.line',
        'Line', readonly=True)
    edi_shipment = fields.Many2One('edi.shipment.in',
        'Shipment', readonly=True)

    @classmethod
    def get_resource(cls):
        'Return list of Model names for resource Reference'
        return [(None, ''),
                ('stock.shipment.in', 'Shipment'),
                ('purchase.purchase', 'Purchase'),
                ('purchase.line', 'Line'),
                ('stock.move', 'Move')]

    def read_message(self, message):
        if message:
            message.pop(0)
        type_ = message.pop(0) if message else ''
        value = message.pop(0) if message else ''
        self.type_ = type_
        self.value = value

    def search_reference(self):
        model = None
        if self.type_ == 'DQ':
            model = 'stock.shipment.in'
        elif self.type_ == 'ON':
            model = 'purchase.purchase'
        if not model:
            return

        Model = Pool().get(model)
        res = Model.search([('number', '=', self.reference)], limit=1)
        self.origin = res[0] if res else None


# class EdiShipmentInTransport(ModelSQL, ModelView):
#     'Edi Shipment in Transport'
#     __name__ = 'edi.shipment.in.transport'
#     # TDT
#     mode = fields.Selection([('10', 'Maritime'), ('20', 'Train'),
#         ('30', 'Road'), ('40', 'airplaine'), ('60', 'Multimode')],
#         'Transport Mode', readonly=True)
#     qualifier = fields.Selection([('20', 'Principal Transport')],
#         'Qualifier for Transort', readonly=True)
#     name = fields.char('Name', readonly=True)
#
# class EdiShipmentInPackageSequence(ModelSQL, ModelView):
#     'Edi Shipment in Package Sequence'
#     __name__ = 'edi.shipment.in.package_sequence'
#     # CPS
#     number = fields.Integer('Number', readonly=True)
#     predecessor = fields.Integer('Preedcessor', readonly=True)
#
# class EdiShipmentInPackage(ModelSQL, ModelView):
#     'Edi Shipment in Package'
#     __name__ = 'edi.shipment.in.package'
#     # PAC
#     quantity = fields.Integer('Number', readonly=True)
#     type_ = fields.selection([('08', 'Non-returnable pallet'),
#         ('09', 'returnable pallet'), ('200', 'ISO half pallet 0'),
#         ('201', 'ISO pallet 1'), ('BE', 'Package'), ('BX', 'Box'),
#         ('CT', 'Cardboard box'), ('CS', 'Rigid box'),
#         ('DH', 'CHEP plastic box'), ('PC', 'Package / Piece'),
#         ('PK', 'Package / Packaging'), ('RO', 'Roll'),
#         ('SL', 'Plastic plate'), ('SW', 'Shrink')], 'Package Type',
#         readonly=True)
#
# class EdiShipmentInManipulation(ModelSQL, ModelView):
#     'Edi Shipment in Manipulation'
#     __name__ = 'edi.shipment.in.manipulation'
#     # HAN
#     code = fields.Char('Code', readonly=True)
#     description = fields.Char('Description', readonly=True)
#
# class EdiShipmentInPackageIdentification(ModelSQL, ModelView):
#     'Edi Shipment in Package Identification'
#     __name__ = 'edi.shipment.in.package_identification'
#     # PCI
#     marking = fields.Char('Marking', readonly=True)
#     qualifier = fields.Char('Qualifier', readonly=True)
#     identity = fields.Char('Identity', readonly=True)

class EdiShipmentInLine(ModelSQL, ModelView):
    'Edi Shipment in Line'
    __name__ = 'edi.shipment.in.line'
    # LIN, PIALIN, IMDLIN, MEALIN, PCILIN
    code = fields.Char('Code', readonly=True)
    code_type = fields.Selection([
        (None, ''),
        ('EAN8', 'EAN8'),
        ('EAN13', 'EAN13'),
        ('EAN14', 'EAN14'),
        ('DUN14', 'DUN14'),
        ('EN', 'EN')],
        'Code Type')
    line_number = fields.Integer('Line Number', readonly=True)
    purchaser_code = fields.Char('Purchaser Code', readonly=True)
    supplier_code = fields.Char('Supplier Code', readonly=True)
    serial_number = fields.Char('Serial Number', readonly=True)
    lot_number = fields.Char('Lot Number', readonly=True)
    description_type = fields.Selection([
        (None, ''),
        ('F', 'Free Description'),
        ('C', 'Codificated Description')],
        'Type of Description', readonly=True)
    description = fields.Char('Description', readonly=True)
    desccod = fields.Selection([
        (None, ''),
        ('CU', 'Consumption Unit'),
        ('DU', 'Dispatch Unit')],
        'Codification description', readonly=True)
    dimension = fields.Selection([
        (None, ''),
        ('TC', 'Temperature')],
        'Dimension', readonly=True)
    dimension_unit = fields.Selection([
        (None, ''),
        ('CEL', 'Celsius Degrees')],
        'Dimension Unit', readonly=True)
    dimension_qualifier = fields.Selection([
        (None, ''),
        ('SO', 'Storage Limit')],
        'Storage Limit', readonly=True)
    dimension_min = fields.Numeric('Min', readonly=True)
    dimension_max = fields.Numeric('Max', readonly=True)
    marking_instructions = fields.Selection([
        (None, ''),
        ('36E', 'Supplier Instructions')],
        'Marking Instructions', readonly=True)
    expiration_date = fields.Date('Expiration Date', readonly=True)
    packing_date = fields.Date('Packing Date', readonly=True)
    planned_date = fields.Date('Planned Date', readonly=True)
    quantities = fields.One2Many('edi.shipment.in.line.qty',
        'edi_shipment_line', 'Quantities')
    references = fields.One2Many('edi.shipment.in.reference',
        'edi_shipment_in_line', 'References')
    edi_shipment = fields.Many2One('edi.shipment.in', 'Shipment',
        readonly=True)
    product = fields.Many2One('product.product', 'Product')
    quantity = fields.Function(fields.Numeric('Quantity', digits=(16, 4)),
        'shipment_quantity')

    def shipment_quantity(self, name):
        for q in self.quantities:
            if q.type_ == '12':
                return q.quantity
        return Decimal('0')

    def read_LIN(self, message):
        def _get_code_type(code):
            for code_type in ('EAN8', 'EAN13', 'EAN'):
                check_code_ean = 'check_code_' + code_type.lower()
                if getattr(barcodenumber, check_code_ean)(code):
                    return code_type
            if len(code) == 14:
                return 'EAN14'
            # TODO DUN14

        self.code = message.pop(0) if message else ''
        code_type = message.pop(0) if message else ''
        if code_type == 'EN':
            self.code_type = _get_code_type(self.code)

        self.line_number = message.pop(0) if message else ''

    def read_PIALIN(self, message):
        self.purchaser_code = message.pop(0) if message else ''
        if message:
            self.supplier_code = message.pop(0)
        if message:
            self.serial_number = message.pop(0)
        if message:
            self.lot_number = message.pop(0)

    def read_IMDLIN(self, message):
        self.description_type = message.pop(0) if message else ''
        self.description = message.pop(0) if message else ''
        if message:
            self.desccod = message.pop(0)

    def read_MEALIN(self, message):
        self.dimension = message.pop(0) if message else ''
        if message:
            self.dimension_unit = message.pop(0)
        if message:
            self.dimension_qualifier = message.pop(0)
        if message:
            self.dimension_min = message.pop(0)
        if message:
            self.dimension_max = message.pop(0)

    def read_QTYLIN(self, message):
        pool = Pool()
        QTY = pool.get('edi.shipment.in.line.qty')

        qty = QTY()
        qty.type_ = message.pop(0) if message else ''
        qty.quantity = to_decimal(message.pop(0), 4) if message else Decimal(0)
        if message:
            qty.unit = message.pop(0)

        if not getattr(self, 'quantities', False):
            self.quantities = []
        self.quantities += (qty, )

    def read_RFFLIN(self, message):
        pool = Pool()
        REF = pool.get('edi.shipment.in.reference')

        ref = REF()
        ref.type_ = message.pop(0) if message else ''
        ref.reference = message.pop(0) if message else ''
        ref.search_reference()
        if not getattr(self, 'references', False):
            self.references = []
        self.references += (ref,)

    def read_PCILIN(self, message):
        self.marking_instructions = message.pop(0) if message else ''
        if message:
            self.expiration_date = to_date(message.pop(0))
        if message:
            self.packing_date = to_date(message.pop(0))
        if message:
            self.lot_number = message.pop(0)

    def read_QVRLIN(self, message):
        pool = Pool()
        QTY = pool.get('edi.shipment.in.line.qty')

        qty = QTY()
        qty.type_ = message.pop(0) if message else ''
        qty.quantity = to_decimal(message.pop(0), 4) if message else Decimal(0)
        qty.difference = message.pop(0) if message else ''
        if not getattr(self, 'quantities', False):
            self.quantities = []
        self.quantities += (qty, )

    def read_DTMLIN(self, message):
        if message:
            self.planned_date = to_date(message.pop(0))

    def read_MOALIN(self, message):
        # Not implemented
        pass

    def read_FTXLIN(self, message):
        # Not implemented
        pass

    def read_LOCLIN(self, message):
        # Not implemented
        pass

    def search_related(self, edi_shipment):
        pool = Pool()
        Barcode = pool.get('product.code')
        REF = pool.get('edi.shipment.in.reference')
        Purchase = pool.get('purchase.purchase')

        domain = [('number', '=', self.code)]
        barcode = Barcode.search(domain, limit=1)
        if not barcode:
            return
        product = barcode[0].product
        self.product = product

        purchases = [x.origin for x in edi_shipment.references if
            x.type_ == 'ON' and isinstance(x.origin, Purchase)]

        self.references = []
        for purchase in purchases:
            for move in purchase.moves:
                if move.product == product:
                    ref = REF()
                    ref.type_ = 'ON'
                    ref.origin = 'stock.move,%s ' % move.id
                    self.references += (ref,)


class EdiShipmentInLineQty(ModelSQL, ModelView):
    'Edi Shipment in Line Qty'
    __name__ = 'edi.shipment.in.line.qty'
    # QTYLIN, QVRLIN
    type_ = fields.Selection([
        (None, ''),
        ('12', 'Quantity Sended'),
        ('59', 'Quantity on package'),
        ('192', 'Free Quantity'),
        ('21', '21'),
        ('45E', '45E')],
        'Quantity Type', readonly=True)
    quantity = fields.Numeric('Quantity', readonly=True)
    unit = fields.Selection([
        (None, ''),
        ('KGM', 'Kilogramo'),
        ('GRM', 'Gramo'),
        ('LTR', 'Litro'),
        ('PCE', 'Pieza'),
        ('EA', 'EA')],
        'Unit', readonly=True)
    difference = fields.Selection([
        (None, ''),
        ('BP', 'Partial Shipment'),
        ('CP', 'Partial Shipment but Complete')],
        'Difference', readonly=True)
    edi_shipment_line = fields.Many2One('edi.shipment.in.line',
        'Shipment Line', readonly=True)


class EdiShipmentIn(Workflow, ModelSQL, ModelView):
    'Edi shipment In'
    __name__ = 'edi.shipment.in'

    company = fields.Many2One('company.company', 'Company', readonly=True)
    number = fields.Char('Number')
    type_ = fields.Selection([
        ('351', 'Expedition Warning')],
        'Document Type')
    function_ = fields.Selection([
        ('9', 'Original'),
        ('31', 'Copy')],
        'Function Type')
    expedition_date = fields.Date('Expedition Date', readonly=True)
    estimated_date = fields.Date('Estimated Date', readonly=True)
    lines = fields.One2Many('edi.shipment.in.line', 'edi_shipment', 'Shipment')
    references = fields.One2Many('edi.shipment.in.reference',
        'edi_shipment', 'References')
    suppliers = fields.One2Many('edi.shipment.supplier', 'edi_shipment',
        'Supplier', readonly=True)
    manual_party = fields.Many2One('party.party', 'Manual Party')
    shipment = fields.Many2One('stock.shipment.in', 'Shipment')
    party = fields.Function(fields.Many2One('party.party', 'Shipment Party'),
        'get_party', searcher='search_party')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ], 'State', required=True, readonly=True, select=True)
    references_stock_moves = fields.Function(fields.One2Many(
        'stock.move', 'edi_shipment', 'References Stock Moves',
        domain=[('stock_type', '=', 'manual')]
        ), 'get_reference_stock_moves')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'cancelled'),
                ('confirmed', 'draft'),
                ('cancelled', 'draft'),
                ('draft', 'cancelled')
                ))
        cls._buttons.update({
            'create_shipment': {},
            'search_references': {},
            'cancel': {
                'invisible': Eval('state') == 'cancelled',
                'icon': 'tryton-cancel',
                'depends': ['state'],
                },
            'draft': {
                'invisible': Eval('state') != 'cancelled',
                'icon': 'tryton-clear',
                'depends': ['state'],
                },
            'confirm': {
                'invisible': Eval('state') != 'draft',
                'icon': 'tryton-forward',
                'depends': ['state'],
                },
            })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def search_party(cls, name, clause):
        return ['OR', ('manual_party', ) + tuple(clause[1:]),
                [('suppliers.type_', '=', 'NADSU'),
                    ('suppliers.party', ) + tuple(clause[1:])]]

    def get_party(self, name):
        if self.manual_party:
            return self.manual_party.id
        for s in self.suppliers:
            if s.type_ == 'NADSU':
                return s.party and s.party.id

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, edi_shipments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, edi_shipments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, edi_shipments):
        pass

    def read_BGM(self, message):
        self.number = message.pop(0) if message else ''
        self.type_ = message.pop(0) if message else ''
        self.function_ = message.pop(0) if message else ''

    def read_DTM(self, message):
        if message:
            self.expedition_date = to_date(message.pop(0))
        if message:
            self.estimated_date = to_date(message.pop(0))

    def read_RFF(self, message):
        pool = Pool()
        REF = pool.get('edi.shipment.in.reference')

        ref = REF()
        ref.type_ = message.pop(0) if message else ''
        if message:
            ref.reference = message.pop(0)
        if message:
            ref.reference_date = to_date(message.pop(0))
        ref.search_reference()
        if not getattr(self, 'references', False):
            self.references = []
        self.references += (ref,)

    def read_TOD(self, message):
        # Not implemented
        pass

    def read_TDT(self, message):
        # Not implemented
        pass

    def read_CPS(self, message):
        # Not implemented
        pass

    def read_PAC(self, message):
        # Not implemented
        pass

    def read_HAN(self, message):
        # Not implemented
        pass

    def read_PCI(self, message):
        # Not implemented
        pass

    def read_ALI(self, message):
        # Not implemented
        pass

    def read_CNTRES(self, message):
        # Not implemented
        pass

    def read_MOA(self, message):
        # Not implemented
        pass

    def read_MEA(self, message):
        # Not implemented
        pass

    def get_quantity(line):
        for qty in line.quantities:
            if qty.type_ == '12':
                return float(qty.quantity)

    def get_reference_stock_moves(self, name=None):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        StockMove = pool.get('stock.move')

        purchase_moves = {}

        for reference in self.references:
            if reference.type_ == 'ON' and reference.origin:
                if isinstance(reference.origin, Purchase):
                    for move in reference.origin.moves:
                        purchase_moves[move.id] = move.quantity

        for line in self.lines:
            for reference in line.references:
                if reference.type_ == 'ON' and reference.origin:
                    if isinstance(reference.origin, StockMove):
                        move = reference.origin
                        if move.id in purchase_moves:
                            purchase_moves[move.id] = (purchase_moves[move.id] -
                                move.quantity)
                            if purchase_moves[move.id] <= 0:
                                purchase_moves.pop(move.id)
                        else:
                            purchase_moves[move.id] = move.quantity

        return [x for x in purchase_moves]

    @classmethod
    def import_edi_file(cls, shipments, data):
        pool = Pool()
        ShipmentEdi = pool.get('edi.shipment.in')
        ShipmentEdiLine = pool.get('edi.shipment.in.line')
        SupplierEdi = pool.get('edi.shipment.supplier')
        # Configuration = pool.get('stock.configuration')

        # config = Configuration(1)
        separator = '|'  # TODO config.separator

        shipment_edi = None
        document_type = data.pop(0).replace('\n', '').replace('\r', '')
        if document_type != 'DESADV_D_96A_UN_EAN005':
            return
        for line in data:
            line = line.replace('\n', '').replace('\r', '')
            line = line.split(separator)
            msg_id = line.pop(0)
            if msg_id == 'BGM':
                shipment_edi = ShipmentEdi()
                shipment_edi.read_BGM(line)
            elif msg_id == 'LIN':
                # if shipment_line:
                #     shipment_line.search_related(shipment)
                shipment_edi_line = ShipmentEdiLine()
                shipment_edi_line.read_LIN(line)
                if not getattr(shipment_edi, 'lines', False):
                    shipment_edi.lines = []
                shipment_edi.lines += (shipment_edi_line,)
            elif 'LIN' in msg_id:
                getattr(shipment_edi_line, 'read_%s' % msg_id)(line)
            elif msg_id in [x[0] for x in SUPPLIER_TYPE]:
                supplier = SupplierEdi()
                getattr(supplier, 'read_%s' % msg_id)(line)
                supplier.search_party()
                if not getattr(shipment_edi, 'suppliers', False):
                    shipment_edi.suppliers = []
                shipment_edi.suppliers += (supplier,)
            elif 'NAD' in msg_id:
                continue
            else:
                getattr(shipment_edi, 'read_%s' % msg_id)(line)

        # invoice_line.search_related(shipment)
        return shipment_edi

    def add_attachment(self, attachment, filename=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        if not filename:
            filename = datetime.now().strftime("%y/%m/%d %H:%M:%S")
        attach = Attachment(
            name=filename,
            type='data',
            data=attachment.decode('utf8'),
            resource=self)
        attach.save()

    @classmethod
    def import_shipment_in(cls, edi_shipments=None):
        pool = Pool()
        Configuration = pool.get('stock.configuration')

        configuration = Configuration(1)
        source_path = os.path.abspath(configuration.inbox_path_edi or
             DEFAULT_FILES_LOCATION)

        files = [os.path.join(source_path, fp) for fp in
                 os.listdir(source_path) if os.path.isfile(os.path.join(
                     source_path, fp))]
        files_to_delete = []
        to_save = []
        attachments = dict()
        for fname in files:
            if fname[-4:].lower() not in KNOWN_EXTENSIONS:
                continue
            with open(fname, 'r', encoding='latin-1') as fp:
                data = fp.readlines()
                shipment = cls.import_edi_file([], data)

            basename = os.path.basename(fname)
            if shipment:
                attachments[shipment] = ("\n".join(data), basename)
                to_save.append(shipment)
                files_to_delete.append(fname)

        if to_save:
            cls.save(to_save)

        # with Transaction().set_user(0, set_context=True):
        #     for shipment, (data, basename) in attachments.items():
        #         shipment.add_attachment(data, basename)

        if files_to_delete:
            for file in files_to_delete:
                os.remove(file)

        cls.search_references(to_save)

    def _get_new_lot(self, line, quantity):
        pool = Pool()
        Lot = pool.get('stock.lot')

        if line.expiration_date:
            lot = Lot()
            lot.product = line.product
            lot.expiration_date = line.expiration_date
            lot.on_change_product()
            return lot

    @classmethod
    @ModelView.button
    def search_references(cls, edi_shipments):
        pool = Pool()
        Line = pool.get('edi.shipment.in.line')

        to_save = []
        for edi_shipment in edi_shipments:
            if edi_shipment.shipment:
                continue
            for eline in edi_shipment.lines:
                eline.search_related(edi_shipment)
                to_save.append(eline)
        Line.save(to_save)

    @classmethod
    @ModelView.button
    def create_shipment(cls, edi_shipments):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        Move = pool.get('stock.move')
        Purchase = pool.get('purchase.purchase')

        default_values = ShipmentIn.default_get(ShipmentIn._fields.keys(),
                with_rec_name=False)

        to_save = []
        move_to_save = []
        for edi_shipment in edi_shipments:
            if edi_shipment.shipment:
                continue

            shipment = ShipmentIn(**default_values)
            for reference in edi_shipment.references:
                if reference.type_ == 'ON' and reference.origin:
                    if isinstance(reference.origin, Purchase):
                        shipment.warehouse = reference.origin.warehouse
                        break

                if reference.type_ == 'ON' and not reference.origin:
                    raise UserError(gettext(
                                'stock_shipment_in_edi.msg_no_purchase_ref'))

            shipment.reference = edi_shipment.number
            shipment.supplier = edi_shipment.party
            shipment.on_change_supplier()
            edi_shipment.shipment = shipment

            for line in edi_shipment.lines:
                if not line.product:
                    raise UserError(gettext(
                            'stock_shipment_in_edi.msg_no_product',
                            number=line.line_number))

                if not line.references:
                    raise UserError(gettext(
                            'stock_shipment_in_edi.msg_no_move_ref',
                            number=line.line_number))

                for ref in line.references:
                    if ref.origin not in move_to_save:
                        quantity = cls.get_quantity(line)
                        move = ref.origin
                        move.shipment = shipment
                        move.quantity = quantity
                        move.lot = cls._get_new_lot(cls, line, quantity)
                        move.planned_date = line.planned_date
                        move_to_save.append(move)
                    else:
                        quantity = cls.get_quantity(line)
                        move, = ref.origin.copy([ref.origin])
                        move.shipment = shipment
                        move.quantity = quantity
                        move.lot = cls._get_new_lot(cls, line, quantity)
                        move.planned_date = line.planned_date
                        move_to_save.append(move)

            edi_shipment.save()
            to_save.append(shipment)

        if to_save:
            ShipmentIn.save(to_save)

        if move_to_save:
            Move.save(move_to_save)
