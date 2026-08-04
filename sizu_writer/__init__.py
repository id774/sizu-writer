#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/__init__.py: Package root of sizu-writer
#
#  Description:
#  This module holds the data class that carries one generation result
#  through the whole system and the package version. It imports nothing
#  beyond the standard library, so every other module can import it
#  without pulling in Flask or the OpenAI client.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v2.0 2026-08-05
#       Carry the version of the provider neutral generation settings.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

from dataclasses import dataclass, field
from typing import List

__version__ = "2.0"


@dataclass
class Draft:
    """ One generation result: the post body and its title candidates. """

    body: str
    primary_title: str
    alternative_titles: List[str] = field(default_factory=list)
    model: str = ""
    generated_at: str = ""
    notices: List[str] = field(default_factory=list)
