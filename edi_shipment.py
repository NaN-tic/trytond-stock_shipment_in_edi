# -*- coding: utf-8 -*
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool, PoolMeta
# from trytond.pyson import Eval, Bool, Or
from trytond.transaction import Transaction
import os
from trytond.modules.account_invoice_edi.invoice import (SupplierEdiMixin,
    SUPPLIER_TYPE)
# from trytond.exceptions import UserError, UserWarning
# from trytond.i18n import gettext
from datetime import datetime
from decimal import Decimal

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

class SupplierEdi(SupplierEdiMixin, ModelSQL, ModelView):
    'Supplier Edi'
    __name__ = 'edi.shipment.supplier'

    edi_shipment = fields.Many2One('edi.shipment.in', 'Edi Shipment')


class EdiShipmentReference(ModelSQL, ModelView):
    'Account Invoice Reference'
    __name__ = 'edi.shipment.in.reference'

    # RFF, RFFLIN
    type_ = fields.Selection([('', ''), ('DQ', 'Shipment'), ('ON', 'Purchase'),
        ('LI', 'Line Number'), ('VN', 'VN')],
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
        return [(None, ''), ('stock.shipment.in', 'Shipment'),
            ('purchase.purchase', 'Purchase'),
            ('purchase.line', 'Line'), ('stock.move', 'Move')]

    def read_message(self, message):
        message.pop(0)
        type_ = message.pop(0)
        value = message.pop(0)
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
        self.origin = None
        if res != []:
            self.origin = res[0]

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
    code_type = fields.Selection([('', ''), ('EAN8', 'EAN8'),
        ('EAN13', 'EAN13'), ('EAN14', 'EAN14'), ('DUN14', 'DUN14'),
        ('EN', 'EN')], 'Code Type')
    line_number = fields.Integer('Line Number', readonly=True)
    purchaser_code = fields.Char('Purchaser Code', readonly=True)
    supplier_code = fields.Char('Supplier Code', readonly=True)
    serial_number = fields.Char('Serial Number', readonly=True)
    lot_number = fields.Char('Lot Number', readonly=True)
    description_type = fields.Selection([('', ''), ('F', 'Free Description'),
        ('C', 'Codificated Description')], 'Type of Description',
        readonly=True)
    description = fields.Char('Description', readonly=True)
    desccod = fields.Selection([('', ''), ('CU', 'Consumption Unit'),
        ('DU', 'Dispatch Unit')], 'Codification description', readonly=True)
    dimension = fields.Selection([('', ''), ('TC', 'Temperature')],
        'Dimension', readonly=True)
    dimension_unit = fields.Selection([('', ''), ('CEL', 'Celsius Degrees')],
        'Dimension Unit', readonly=True)
    dimension_qualifier = fields.Selection([('', ''), ('SO', 'Storage Limiet')],
        'Storage Limiet', readonly=True)
    dimension_min = fields.Numeric('Min', readonly=True)
    dimension_max = fields.Numeric('Max', readonly=True)
    marking_instructions = fields.Selection([('', ''),
        ('36E', 'Supplier Instructions')], 'Marking Instructions',
        readonly=True)
    expiration_date = fields.Date('Expiration Date', readonly=True)
    packing_date = fields.Date('Packing Date', readonly=True)
    quantities = fields.One2Many('edi.shipment.in.line.qty',
        'edi_shipment_line', 'Quantities')
    references = fields.One2Many('edi.shipment.in.reference',
        'edi_shipment_in_line', 'References')
    edi_shipment = fields.Many2One('edi.shipment.in', 'Shipment', readonly=True)
    product = fields.Many2One('product.product', 'Product')

    def read_LIN(self, message):
        self.code = message.pop(0)
        self.code_type = message.pop(0)
        self.line_number = message.pop(0)

    def read_PIALIN(self, message):
        self.purchaser_code = message.pop(0)
        if message:
            self.supplier_code = message.pop(0)
        if message:
            self.serial_number = message.pop(0)
        if message:
            self.lot_number = message.pop(0)

    def read_IMDLIN(self, message):
        self.description_type = message.pop(0)
        self.description = message.pop(0)
        if message:
            self.desccod = message.pop(0)

    def read_MEALIN(self, message):
        self.dimension = message.pop(0)
        if message:
            self.dimension_unit = message.pop(0)
        if message:
            self.dimension_qualifier = message.pop(0)
        if message:
            self.dimension_min = message.pop(0)
        if message:
            self.dimension_max = message.pop(0)

    def read_QTYLIN(self, message):
        QTY = Pool().get('edi.shipment.in.line.qty')
        qty = QTY()
        qty.type_ = message.pop(0)
        qty.quantity = to_decimal(message.pop(0), 4)
        if message:
            qty.unit = message.pop(0)

        if not getattr(self, 'quantities', False):
            self.quantities = []
        self.quantities += (qty, )

    def read_RFFLIN(self, message):
        REF = Pool().get('edi.shipment.in.reference')
        ref = REF()
        ref.type_ = message.pop(0)
        ref.reference = message.pop(0)
        ref.search_reference()
        if not getattr(self, 'references', False):
            self.references = []
        self.references += (ref,)

    def read_PCILIN(self, message):
        self.marking_instructions = message.pop(0)
        if message:
            self.expiration_date = to_date(message.pop(0))
        if message:
            self.packing_date = to_date(message.pop(0))
        if message:
            self.lot_number = message.pop(0)

    def read_QVRLIN(self, message):
        QTY = Pool().get('edi.shipment.in.line.qty')
        qty = QTY()
        qty.type_ = message.pop(0)
        qty.quantity = to_decimal(message.pop(0), 4)
        qty.difference = message.pop(0)
        if not getattr(self, 'quantities', False):
            self.quantities = []
        self.quantities += (qty, )

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
        REF = Pool().get('edi.shipment.in.reference')
        domain = [('number', '=', self.code)]
        barcode = Barcode.search(domain, limit=1)
        if not barcode:
            return
        product = barcode[0].product
        self.product = product

        purchases = [x.origin for x in edi_shipment.references if
            x.type_ == 'ON' and x.origin]
        self.references = []
        for purchase in purchases:
            for move in purchase.moves:
                if move.product == product:
                    ref = REF()
                    ref.type_ = 'move'
                    ref.origin = 'stock.move,%s ' % move.id
                    self.references += (ref,)


class EdiShipmentInLineQty(ModelSQL, ModelView):
    'Edi Shipment in Line Qty'
    __name__ = 'edi.shipment.in.line.qty'
    # QTYLIN, QVRLIN
    type_ = fields.Selection([('', ''), ('12', 'Quantity Sended'),
        ('59', 'Quantity on package'), ('192', 'Free Quantity'),
        ('21', '21'), ('45E', '45E')],
        'Quantity Type', readonly=True)
    quantity = fields.Numeric('Quantity', readonly=True)
    unit = fields.Selection([('', ''), ('KGM', 'Kilogramo'), ('GRM', 'Gramo'),
        ('LTR', 'Litro'), ('PCE', 'Pieza'), ('EA', 'EA')], 'Unit',
        readonly=True)
    difference = fields.Selection([('', ''), ('BP', 'Partial Shipment'),
        ('CP', 'Partial Shipment but Complete')], 'Difference', readonly=True)
    edi_shipment_line = fields.Many2One('edi.shipment.in.line', 'Shipment Line',
        readonly=True)

class EdiShipmentIn(ModelSQL, ModelView):
    'Edi shipment In'
    __name__ = 'edi.shipment.in'

    company = fields.Many2One('company.company', 'Company', readonly=True)
    number = fields.Char('Number')
    type_ = fields.Selection([('351', 'Expedition Warning')],
        'Document Type')
    function_ = fields.Selection([('9', 'Original'),
        ('31', 'Copy')], 'Function Type')
    expedition_date = fields.Date('Expedition Date', readonly=True)
    estimated_date = fields.Date('Estimated Date', readonly=True)
    lines = fields.One2Many('edi.shipment.in.line', 'edi_shipment', 'Shipment')
    references = fields.One2Many('edi.shipment.in.reference',
        'edi_shipment', 'References')
    suppliers = fields.One2Many('edi.shipment.supplier', 'edi_shipment',
        'Supplier', readonly=True)
    manual_party = fields.Many2One('party.party', 'Manual Party')
    shipment = fields.Many2One('stock.shipment.in', 'Shipment')
    party = fields.Function(fields.Many2One('party.party', 'Invoice Party'),
        'get_party', searcher='search_party')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'create_shipments': {},
            'search_references': {}
        })

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

    def read_BGM(self, message):
        self.number = message.pop(0)
        self.type_ = message.pop(0)
        self.function_ = message.pop(0)

    def read_DTM(self, message):
        if message:
            self.expedition_date = to_date(message.pop(0))
        if message:
            self.estimated_date = to_date(message.pop(0))

    def read_RFF(self, message):
        REF = Pool().get('edi.shipment.in.reference')
        ref = REF()
        ref.type_ = message.pop(0)
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

    @classmethod
    def import_edi_file(cls, shipments, data):
        pool = Pool()
        Shipment = pool.get('edi.shipment.in')
        Line = pool.get('edi.shipment.in.line')
        SupplierEdi = pool.get('edi.shipment.supplier')
        # Configuration = pool.get('stock.configuration')

        # config = Configuration(1)
        separator = '|'  # TODO config.separator

        shipment = None
        shipment_line = None
        document_type = data.pop(0).replace('\n', '').replace('\r', '')
        if document_type != 'DESADV_D_96A_UN_EAN005':
            return
        for line in data:
            line = line.replace('\n', '').replace('\r', '')
            line = line.split(separator)
            msg_id = line.pop(0)
            if msg_id == 'BGM':
                shipment = Shipment()
                shipment.read_BGM(line)
            elif msg_id == 'LIN':
                # if shipment_line:
                #     shipment_line.search_related(shipment)
                shipment_line = Line()
                shipment_line.read_LIN(line)
                if not getattr(shipment, 'lines', False):
                    shipment.lines = []
                shipment.lines += (shipment_line,)
            elif 'LIN' in msg_id:
                getattr(shipment_line, 'read_%s' % msg_id)(line)
            elif msg_id in [x[0] for x in SUPPLIER_TYPE]:
                supplier = SupplierEdi()
                getattr(supplier, 'read_%s' % msg_id)(line)
                supplier.search_party()
                if not getattr(shipment, 'suppliers', False):
                    shipment.suppliers = []
                shipment.suppliers += (supplier,)
            elif 'NAD' in msg_id:
                continue
            else:
                getattr(shipment, 'read_%s' % msg_id)(line)

        # invoice_line.search_related(shipment)
        return shipment

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
                print("fname:", fname)
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

        # if files_to_delete:
        #     for file in files_to_delete:
        #         os.remove(file)

        cls.search_references(to_save)

    @classmethod
    @ModelView.button
    def search_references(cls, edi_shipments):
        Line = Pool().get('edi.shipment.in.line')
        to_save = []
        for edi_shipment in edi_shipments:
            if edi_shipment.shipment:
                continue
            for eline in edi_shipment.lines:
                eline.search_related(edi_shipment)
                to_save.append(eline)
        Line.save(to_save)
