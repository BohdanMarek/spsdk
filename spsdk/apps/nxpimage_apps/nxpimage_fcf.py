#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2025 NXP
#
# SPDX-License-Identifier: BSD-3-Clause
"""Nxpimage FCF group."""

import logging

import click

from spsdk.apps.utils.common_cli_options import (
    SpsdkClickGroup,
    spsdk_config_option,
    spsdk_family_option,
    spsdk_output_option,
)
from spsdk.image.fcf.fcf import FCF
from spsdk.utils.config import Config
from spsdk.utils.family import FamilyRevision
from spsdk.utils.misc import get_printable_path, load_binary, write_file

logger = logging.getLogger(__name__)


@click.group(name="fcf", cls=SpsdkClickGroup)
def fcf_group() -> None:  # pylint: disable=unused-argument
    """Group of sub-commands related to FCF block."""


@fcf_group.command(name="get-template", no_args_is_help=True)
@spsdk_family_option(families=FCF.get_supported_families())
@spsdk_output_option(force=True)
def fcf_get_template_command(output: str, family: FamilyRevision) -> None:
    """Create template of configuration in YAML format."""
    fcf_get_template(output, family)


def fcf_get_template(output: str, family: FamilyRevision) -> None:
    """Create template of configuration in YAML format."""
    click.echo(f"Creating {get_printable_path(output)} template file.")
    write_file(FCF.get_config_template(family), output)


@fcf_group.command(name="export", no_args_is_help=True)
@spsdk_config_option(klass=FCF)
@spsdk_output_option()
def fcf_export_command(config: Config, output: str) -> None:
    """Generate FCF from YAML/JSON configuration.

    The configuration template files could be generated by subcommand 'get-template'.
    """
    fcf_export(config, output)


def fcf_export(config: Config, output: str) -> None:
    """Export FCF from YAML/JSON configuration."""
    fcf_image = FCF.load_from_config(config)
    fcf_data = fcf_image.export()
    write_file(fcf_data, output, mode="wb")

    logger.info(f"Created FCF Image:\n{str(fcf_image.registers.image_info())}")
    click.echo(f"Success. (FCF: {output} created.)")


@fcf_group.command(name="parse", no_args_is_help=True)
@click.option(
    "-b",
    "--binary",
    type=click.Path(exists=True, readable=True, resolve_path=True),
    required=True,
    help="Path to binary FCF to parse.",
)
@spsdk_family_option(families=FCF.get_supported_families())
@spsdk_output_option()
def fcf_parse_command(binary: str, family: FamilyRevision, output: str) -> None:
    """Parse FCF."""
    fcf_parse(binary, family, output)


# pylint: disable=unused-argument  # preparation for future updates
def fcf_parse(binary: str, family: FamilyRevision, output: str) -> None:
    """Parse FCF Image into YAML configuration."""
    fcf_image = FCF.parse(load_binary(binary), family=family)
    logger.info(f"Parsed FCF image memory map: {fcf_image.registers.image_info().draw()}")
    config = fcf_image.get_config_yaml()
    write_file(config, output)
    click.echo(f"Success. (FCF: {binary} has been parsed and stored into {output}.)")
