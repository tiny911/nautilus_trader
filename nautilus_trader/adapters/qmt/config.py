#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

"""
The `config` module provides configuration classes for QMT integration.
"""

from typing import Optional

from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig


class QMTDataClientConfig(LiveDataClientConfig, frozen=True):
    """
    Configuration for the QMT data client.
    """

    qmt_path: Optional[str] = None
    """The path to QMT installation."""


class QMTExecutionClientConfig(LiveExecClientConfig, frozen=True):
    """
    Configuration for the QMT execution client.
    """

    account_id: str
    """The QMT account identifier."""
    qmt_path: Optional[str] = None
    """The path to QMT installation."""
