# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2014  Rafael da Silva Lima - KMEE, www.kmee.com.br
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

class NfeInvoiceCancel(osv.osv):
    _name = 'nfe.invoice_cancel'

    _columns = {
        'justificativa': fields.text('Justificativa', size=255, required=True)
    }

    def _check_name(self, cr, uid, ids, context=None):
        for nfe in self.browse(cr, uid, ids, context=context):
            if not (len(nfe.justificativa) >= 15):
                return False
        return True

    _constraints = [
        (_check_name,
         'Tamanho de justificativa inválida !',
         ['justificativa'])]

    def action_enviar_cancelamento(self, cr, uid, ids, context=None):
        for cancel in self.browse(cr, uid, ids, context=context):
            obj_invoice = self.pool['account.invoice'].browse(
                context['active_id'])
            obj_invoice.cancel_invoice_online(cr, uid, ids, cancel.justificativa, context=context)
        return {'type': 'ir.actions.act_window_close'}
