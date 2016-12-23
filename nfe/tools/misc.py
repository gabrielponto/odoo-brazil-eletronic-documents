# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2016  Renato Lima - Akretion
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

from openerp.tools import config
from openerp.tools.translate import _
from openerp.addons.nfe._openerp.exceptions import RedirectWarning
from openerp.addons.l10n_br_base.tools.misc import punctuation_rm
import sys
import appdirs
import openerp.release as release

def _get_default_datadir():
    home = os.path.expanduser('~')
    if os.path.exists(home):
        func = appdirs.user_data_dir
    else:
        if sys.platform in ['win32', 'darwin']:
            func = appdirs.site_data_dir
        else:
            func = lambda **kwarg: "/var/lib/%s" % kwarg['appname'].lower()
    # No "version" kwarg as session and filestore paths are shared against series
    return func(appname=release.product_name, appauthor=release.author)

def mount_path_nfe(company, document='nfe'):
    db_name = company._cr.dbname
    cnpj = punctuation_rm(company.cnpj_cpf)

    #filestore = config.filestore(db_name)
    filestore = os.path.join(_get_default_datadir(), 'filestore', db_name)
    nfe_path = '/'.join([filestore, 'PySPED', document, cnpj])
    if not os.path.exists(nfe_path):
        try:
            os.makedirs(nfe_path)
        except OSError:
            raise RedirectWarning(
                _(u'Erro!'),
                _(u"""Verifique as permissões de escrita
                    e o caminho da pasta"""))
    return nfe_path
