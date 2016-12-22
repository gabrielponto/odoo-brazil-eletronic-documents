# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2014 KMEE (http://www.kmee.com.br)
#    @author  Rafael da Silva Lima <rafael.lima@kmee.com.br>
#             Matheus Lima Felix <matheus.felix@kmee.com.br>
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

from openerp.osv import osv, fields
from openerp.addons.nfe.sped.nfe.processing.xml import send_correction_letter


class NfeInvoiceCce(osv.TransientModel):

    _name = 'nfe.invoice_cce'

    _columns = {
        'mensagem': fields.text('Mensagem', required=True)
    }

    def _check_name(self, cr, uid, ids, context=None):
        for nfe in self.browse(cr, uid, ids, context=context):
            if not (len(nfe.mensagem) >= 15):
                return False
        return True

    _constraints = [
        (_check_name,
         'Tamanho de mensagem inválida !',
         ['mensagem'])]

    def action_enviar_carta(self, cr, uid, ids, context=None):
        correcao = self.mensagem
        obj_invoice = self.pool['account.invoice'].browse(
            context.get('active_id'))
        obj_cce = self.pool['l10n_br_account.invoice.cce']

        for invoice in obj_invoice:
            chave_nfe = invoice.nfe_access_key

            event_obj = self.pool['l10n_br_account.document_event']
            domain = [('invoice_id', '=', invoice.id)]
            sequencia = len(obj_cce.search(domain)) + 1
            results = []
            try:
                processo = send_correction_letter(
                    invoice.company_id,
                    chave_nfe,
                    sequencia,
                    correcao)
                vals = {
                    'type': str(processo.webservice),
                    'status': processo.resposta.retEvento[0].infEvento.
                    cStat.valor,
                    'response': '',
                    'company_id': invoice.company_id.id,
                    'origin': '[CC-E] ' + str(invoice.internal_number),
                    'message': processo.resposta.retEvento[0].infEvento.
                    xEvento.valor,
                    'state': 'done',
                    'document_event_ids': invoice.id}
                results.append(vals)
                obj_invoice.attach_file_event(
                    sequencia,
                    'cce',
                    'xml')

            except Exception as e:
                vals = {
                    'type': '-1',
                    'status': '000',
                    'response': 'response',
                    'company_id': invoice.company_id.id,
                    'origin': '[CC-E]' + str(invoice.internal_number),
                    'file_sent': 'False',
                    'file_returned': 'False',
                    'message': 'Erro desconhecido ' + e.message,
                    'state': 'done',
                    'document_event_ids': invoice.id,
                }
                results.append(vals)
            finally:
                for result in results:
                    event_obj.create(result)
                    obj_cce.create(cr, uid, {'invoice_id': invoice.id,
                                    'motivo': correcao,
                                    'sequencia': sequencia,
                                    }, context=context)
        return {'type': 'ir.actions.act_window_close'}
