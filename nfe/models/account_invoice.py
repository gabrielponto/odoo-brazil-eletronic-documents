# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2013  Danimar Ribeiro 26/06/2013
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

import os
import logging
import datetime

from openerp.tools.translate import _
from openerp.osv import fields, osv
from openerp.addons.nfe._openerp.exceptions import RedirectWarning

from openerp.addons.nfe.sped.nfe.nfe_factory import NfeFactory
from openerp.addons.nfe.sped.nfe.validator.xml import XMLValidator
from openerp.addons.nfe.sped.nfe.processing.xml import send, cancel
from openerp.addons.nfe.sped.nfe.processing.xml import monta_caminho_nfe
from openerp.addons.nfe.sped.nfe.validator.config_check import \
    validate_nfe_configuration, validate_invoice_cancel

_logger = logging.getLogger(__name__)


class AccountInvoice(osv.osv):
    """account_invoice overwritten methods"""
    _inherit = 'account.invoice'

    _columns = {
        'cce_document_event_ids': fields.one2many(
        'l10n_br_account.invoice.cce', 'invoice_id', u'Eventos'),
        'document_event_ids': fields.one2many('l10n_br_account.document_event', 'document_event_ids', u'Documentos Fiscais'),
    }

    def attach_file_event(self, cr, uid, ids, seq, att_type, ext, context=None):
        """
        Implemente esse metodo na sua classe de manipulação de arquivos
        :param cr:
        :param uid:
        :param ids:
        :param seq:
        :param att_type:
        :param ext:
        :param context:
        :return:
        """
        return False

    def _get_nfe_factory(self, nfe_version):
        return NfeFactory().get_nfe(nfe_version)

    def nfe_export(self, cr, uid, ids, context=None):

        for inv in self.browse(cr, uid, ids):
            # Força a exportação ser manual
            inv.write({'state': 'sefaz_export'})
            continue
            validate_nfe_configuration(inv.company_id)

            nfe_obj = self._get_nfe_factory(inv.nfe_version)

            # nfe_obj = NFe310()
            nfes = nfe_obj.get_xml(cr, uid, ids,
                                   int(inv.company_id.nfe_environment),
                                   context)

            for nfe in nfes:
                # erro = nfe_obj.validation(nfe['nfe'])
                erro = XMLValidator.validation(nfe['nfe'], nfe_obj)
                nfe_key = nfe['key'][3:]
                if erro:
                    raise RedirectWarning(
                        erro, _(u'Erro na validaço da NFe!'))

                inv.write({'nfe_access_key': nfe_key})
                save_dir = os.path.join(
                    monta_caminho_nfe(
                        inv.company_id,
                        chave_nfe=nfe_key) +
                    'tmp/')
                nfe_file = nfe['nfe'].encode('utf8')

                file_path = save_dir + nfe_key + '-nfe.xml'
                try:
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    f = open(file_path, 'w')
                except IOError:
                    raise RedirectWarning(
                        _(u'Erro!'), _(u"""Não foi possível salvar o arquivo
                            em disco, verifique as permissões de escrita
                            e o caminho da pasta"""))
                else:
                    f.write(nfe_file)
                    f.close()

                    event_obj = self.pool['l10n_br_account.document_event']
                    event_obj.create(cr, uid, {
                        'type': '0',
                        'company_id': inv.company_id.id,
                        'origin': '[NF-E]' + inv.internal_number,
                        'file_sent': file_path,
                        'create_date': datetime.datetime.now(),
                        'state': 'draft',
                        'document_event_ids': inv.id
                    }, context=context)
                    inv.write({'state': 'sefaz_export'})

    def action_invoice_send_nfe(self, cr, uid, ids, context=None):

        for inv in self.browse(cr, uid, ids, context=context):

            event_obj = self.pool['l10n_br_account.document_event']
            try:
                event = max(
                    event_obj.search(cr, uid, [('document_event_ids', '=', inv.id),
                                    ('type', '=', '0')]))
            except ValueError:
                raise osv.except_osv('Erro', u'Você deve exportar o XML da Nota Fiscal Primeiro')
            event = event_obj.browse(cr, uid, event, context=context)
            arquivo = event.file_sent
            nfe_obj = self._get_nfe_factory(inv.nfe_version)

            nfe = []
            results = []
            protNFe = {}
            protNFe["state"] = 'sefaz_exception'
            protNFe["status_code"] = ''
            protNFe["message"] = ''
            protNFe["nfe_protocol_number"] = ''
            try:
                nfe.append(nfe_obj.set_xml(arquivo))
                for processo in send(inv.company_id, nfe):
                    vals = {
                        'type': str(processo.webservice),
                        'status': processo.resposta.cStat.valor,
                        'response': '',
                        'company_id': inv.company_id.id,
                        'origin': '[NF-E]' + inv.internal_number,
                        # TODO: Manipular os arquivos manualmente
                        # 'file_sent': processo.arquivos[0]['arquivo'],
                        # 'file_returned': processo.arquivos[1]['arquivo'],
                        'message': processo.resposta.xMotivo.valor,
                        'state': 'done',
                        'document_event_ids': inv.id}
                    results.append(vals)
                    if processo.webservice == 1:
                        for prot in processo.resposta.protNFe:
                            protNFe["status_code"] = prot.infProt.cStat.valor
                            protNFe["nfe_protocol_number"] = \
                                prot.infProt.nProt.valor
                            protNFe["message"] = prot.infProt.xMotivo.valor
                            vals["status"] = prot.infProt.cStat.valor
                            vals["message"] = prot.infProt.xMotivo.valor
                            if prot.infProt.cStat.valor in ('100', '150'):
                                protNFe["state"] = 'open'
                            elif prot.infProt.cStat.valor in ('110', '301',
                                                              '302'):
                                protNFe["state"] = 'sefaz_denied'
                        self.attach_file_event(cr, uid, ids, None, 'nfe', 'xml', context=context)
                        self.attach_file_event(cr, uid, ids, None, None, 'pdf', context=context)
            except Exception as e:
                _logger.error(e.message, exc_info=True)
                vals = {
                    'type': '-1',
                    'status': '000',
                    'response': 'response',
                    'company_id': inv.company_id.id,
                    'origin': '[NF-E]' + inv.internal_number,
                    'file_sent': 'False',
                    'file_returned': 'False',
                    'message': 'Erro desconhecido ' + str(e),
                    'state': 'done',
                    'document_event_ids': inv.id
                }
                results.append(vals)
            finally:
                for result in results:
                    if result['type'] == '0':
                        event_obj.write(cr, uid, [event.id], result, context=context)
                    else:
                        event_obj.create(cr, uid, result, context=context)

                self.write(cr, uid, ids, {
                    'nfe_status': protNFe["status_code"] + ' - ' +
                    protNFe["message"],
                    'nfe_date': datetime.datetime.now(),
                    'state': protNFe["state"],
                    'nfe_protocol_number': protNFe["nfe_protocol_number"],
                })
        return True

    #def button_cancel(self, cr, uid, ids, context=None):
        # was api.multi
    #    for invoice in self.browse(cr, uid, ids, context=context):
    #        document_serie_id = invoice.document_serie_id
    #        fiscal_document_id = invoice.document_serie_id.fiscal_document_id
    #        electronic = invoice.document_serie_id.fiscal_document_id.electronic
    #        #nfe_protocol = invoice.nfe_protocol_number

            #if ((document_serie_id and fiscal_document_id and not electronic) or
            #        not nfe_protocol):
   #         if document_serie_id and fiscal_document_id and not electronic:
   #             return super(AccountInvoice, self).action_cancel(cr, uid, ids, context=context)
   #         else:
   #             result = self.pool['ir.actions.act_window'].for_xml_id(
   #                 'nfe',
   #                 'action_nfe_invoice_cancel_form')
   #             return result

    def cancel_invoice_online(self, cr, uid, ids, justificative, context=None):
        # was api.multi
        event_obj = self.pool['l10n_br_account.document_event']

        for inv in self.browse(cr, uid, ids, context=context):
            if inv.state in ('open', 'paid'):

                validate_nfe_configuration(self.company_id)
                validate_invoice_cancel(inv)

                results = []
                try:
                    processo = cancel(
                        self.company_id,
                        inv.nfe_access_key,
                        inv.nfe_protocol_number,
                        justificative)
                    vals = {
                        'type': str(processo.webservice),
                        'status': processo.resposta.cStat.valor,
                        'response': '',
                        'company_id': self.company_id.id,
                        'origin': '[NF-E] {0}'.format(inv.internal_number),
                        'message': processo.resposta.xMotivo.valor,
                        'state': 'done',
                        'document_event_ids': inv.id}

                    self.attach_file_event(cr, uid, ids, None, 'can', 'xml', context=context)

                    for prot in processo.resposta.retEvento:
                        vals["status"] = prot.infEvento.cStat.valor
                        vals["message"] = prot.infEvento.xEvento.valor
                        if vals["status"] in (
                                '101',  # Cancelamento de NF-e
                                # homologado
                                '128',
                                # Loto do evento processado
                                '135',  # Evento registrado e
                                # vinculado a NFC-e
                                '151',  # Cancelamento de NF-e
                                # homologado fora de prazo
                                '155'):  # Cancelamento homologado fora prazo
                            # Fixme:
                            result = super(AccountInvoice, self)\
                                .action_cancel()
                            if result:
                                self.write(cr, uid, ids, {'state': 'sefaz_cancelled',
                                            'nfe_status': vals["status"] +
                                            ' - ' + vals["message"]
                                            }, context=context)
                                obj_cancel = self.pool[
                                    'l10n_br_account.invoice.cancel']
                                obj_cancel.create(cr, uid, {
                                    'invoice_id': inv.id,
                                    'justificative': justificative,
                                }, context=context)
                    results.append(vals)
                except Exception as e:
                    _logger.error(e.message, exc_info=True)
                    vals = {
                        'type': '-1',
                        'status': '000',
                        'response': 'response',
                        'company_id': self.company_id.id,
                        'origin': '[NF-E] {0}'.format(inv.internal_number),
                        'file_sent': 'OpenFalse',
                        'file_returned': 'False',
                        'message': 'Erro desconhecido ' + e.message,
                        'state': 'done',
                        'document_event_ids': inv.id
                    }
                    results.append(vals)
                finally:
                    for result in results:
                        event_obj.create(cr, uid, result, context=context)

            elif inv.state in ('sefaz_export', 'sefaz_exception'):
                _logger.error(
                    _(u'Invoice in invalid state to cancel online'),
                    exc_info=True)
                # TODO
        return

    def invoice_print(self, cr, uid, ids, context=None):

        for inv in self.browse(cr, uid, ids, context=context):

            document_serie_id = inv.document_serie_id
            fiscal_document_id = inv.document_serie_id.fiscal_document_id
            electronic = inv.document_serie_id.fiscal_document_id.electronic

            if document_serie_id and fiscal_document_id and not electronic:
                return super(AccountInvoice, self).invoice_print()

            assert len(inv.ids) == 1, 'This option should only be ' \
                                      'used for a single id at a time.'

            self.write(cr, uid, ids, {'sent': True}, context=context)
            datas = {
                'ids': inv.ids,
                'model': 'account.invoice',
                'form': self.read(cr, uid, inv.id, context=context)
            }

            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'danfe_account_invoice',
                'datas': datas,
                'nodestroy': True
            }
