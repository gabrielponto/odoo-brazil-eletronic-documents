# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2014  Luis Felipe Mileo - KMEE, www.kmee.com.br
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

from openerp.osv import orm, osv
from openerp.tools.translate import _
from openerp.addons.nfe.sped.nfe.processing.xml import check_key_nfe
from datetime import datetime

class L10n_brAccountDocumentStatusSefaz(osv.TransientModel):

    _inherit = 'l10n_br_account.document_status_sefaz'

    def get_document_status(self, cr, uid, ids, context=None):
        item = self.browse(cr, uid, ids[0], context=context)
        chave_nfe = item.chNFe

        #try:
        processo = check_key_nfe(item.company_id, chave_nfe)

        call_result = {
            'version': processo.resposta.versao.txt,
            'xMotivo': processo.resposta.cStat.txt + ' - ' +
            processo.resposta.xMotivo.txt,
            'cUF': processo.resposta.cUF.txt,
            'chNFe': processo.resposta.chNFe.txt,
            'nfe_environment': processo.resposta.tpAmb.txt,
            'protNFe': '' if processo.resposta.protNFe is None else
            processo.resposta.protNFe.infProt.nProt.txt,
            'retCancNFe': '',
            'procEventoNFe': '',
            'state': 'done',
            'company_id': item.company_id.id,
        }
        self.write(cr, uid, ids, call_result, context=context)

        # write on invoice
        invoice_obj = self.pool['account.invoice']
        if processo.resposta.cStat.txt in ('100', '150'):
            call_result["state"] = 'open'
        elif processo.resposta.cStat.txt in ('110', '301', '302'):
            call_result["state"] = 'sefaz_denied'
        else:
            call_result['state'] = 'sefaz_export'
        invoice_obj.write(cr, uid, invoice_obj.search(cr, uid, [('nfe_access_key', '=', chave_nfe)], context=context), {
            'nfe_status': call_result['xMotivo'],
            'nfe_date': datetime.now(),
            'nfe_protocol_number': call_result['protNFe'],
        })
        #except Exception as e:
            # fixme:
        #    raise orm.except_orm(
        #        _(u'Erro na consulta da chave!'), e)

        mod_obj = self.pool['ir.model.data']
        act_obj = self.pool['ir.actions.act_window']
        result = mod_obj.get_object_reference(cr, uid, 'nfe',
                                              'action_l10n_br_account_product'
                                              '_document_status_sefaz')
        res_id = result and result[1] or False
        result = act_obj.browse(cr, uid, res_id, context=context)
        result.res_id = ids[0]
        return {
            'name':result.name,
            'view_mode': 'form',
            'view_id': result.view_id.id,
            'view_type': 'form',
            'res_model': result.res_model,
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }
