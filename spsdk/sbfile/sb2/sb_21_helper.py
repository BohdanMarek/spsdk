#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2021-2023 NXP
#
# SPDX-License-Identifier: BSD-3-Clause
"""Module containing helper functions for elftosb."""

import struct
from numbers import Number
from typing import Callable, Dict, List, Optional, Union

from spsdk import SPSDKError
from spsdk.mboot.memories import MemId
from spsdk.sbfile.sb2.commands import (
    CmdBaseClass,
    CmdErase,
    CmdFill,
    CmdJump,
    CmdKeyStoreBackup,
    CmdKeyStoreRestore,
    CmdLoad,
    CmdMemEnable,
    CmdProg,
    CmdVersionCheck,
)
from spsdk.utils.crypto import KeyBlob
from spsdk.utils.misc import (
    align_block,
    get_bytes_cnt_of_int,
    load_binary,
    swap32,
    value_to_bytes,
    value_to_int,
)


def get_mem_id(mem_opt: Union[int, str]) -> int:
    """Get memory ID from str or int in BD file.

    :param mem_opt: memory option in BD file
    :raises SPSDKError: if memory option is not supported
    :return: int memory ID
    """
    if isinstance(mem_opt, str):
        mem_id = int(MemId.get_legacy_str(mem_opt))  # type: ignore
    elif isinstance(mem_opt, int):
        mem_id = mem_opt
    if not mem_id:
        raise SPSDKError(f"Unsupported memory option: {mem_opt}")
    return mem_id


def get_command(cmd_name: str) -> Callable[[Dict], CmdBaseClass]:
    """Returns a function based on input argument name.

    The json file generated by bd file parser uses command names (load, fill,
    etc.). These names are used to get the proper function name, which creates
    corresponding object.

    :param cmd_name: one of 'load', 'fill', 'erase', 'enable', 'reset', 'encrypt',
    'keywrap'
    :return: appropriate Command object
    """
    command_object = cmds[cmd_name]
    return command_object


def _fill_memory(cmd_args: dict) -> CmdFill:
    """Returns a CmdFill object initialized based on cmd_args.

    :param cmd_args: dictionary holding address and pattern
    :return: CmdFill object
    """
    address = cmd_args["address"]
    pattern = cmd_args["pattern"]
    # if not isinstance(pattern, bytes):
    #     # convert to bytes
    # pattern = int.to_bytes(pattern, 4, "little")
    return CmdFill(address=address, pattern=pattern)


def _load(cmd_args: dict) -> Union[CmdLoad, CmdProg]:
    """Returns a CmdLoad object initialized based on cmd_args.

    :param cmd_args: dictionary holding path to file or values and address
    :raises SPSDKError: If dict doesn't contain 'file' or 'values' key
    :return: CmdLoad object
    """
    prog_mem_id = 4
    address = cmd_args["address"]
    load_opt = cmd_args.get("load_opt")
    mem_id = 0
    if load_opt:
        mem_id = get_mem_id(load_opt)

    # general non-authenticated load command
    if cmd_args.get("file"):
        data = load_binary(cmd_args["file"])
        return CmdLoad(address=address, data=data, mem_id=mem_id)
    if cmd_args.get("values"):
        # if the memory ID is fuse or IFR change load command to program command
        if mem_id == prog_mem_id:
            return _prog(cmd_args, mem_id)

        values = [int(s, 16) for s in cmd_args["values"].split(",")]
        data = struct.pack(f"<{len(values)}L", *values)
        return CmdLoad(address=address, data=data, mem_id=mem_id)
    if cmd_args.get("pattern"):
        # if the memory ID is fuse or IFR change load command to program command
        # pattern in this case represents 32b int data word 1
        if mem_id == prog_mem_id:
            return _prog(cmd_args, mem_id)

    raise SPSDKError(f"Unsupported LOAD command args: {cmd_args}")


def _prog(cmd_args: dict, mem_id: int) -> CmdProg:
    """Returns a CmdProg object initialized based on cmd_args.

    :param cmd_args: dictionary holding path to file or values and address
    :param int: memory id for programming
    :raises SPSDKError: If data words are wrong
    :return: CmdProg object
    """
    address = cmd_args["address"]
    data_word1 = 0
    data_word2 = 0
    # values provided as binary blob {{aa bb cc dd}} either 4 or 8 bytes:
    if cmd_args.get("values"):
        int_value = int(cmd_args["values"], 16)
        byte_count = get_bytes_cnt_of_int(int_value)

        if byte_count <= 4:
            data_word1 = int_value
        elif byte_count <= 8:
            data_words = value_to_bytes(int_value, byte_cnt=8)
            data_word1 = value_to_int(data_words[:4])
            data_word2 = value_to_int(data_words[4:])
        else:
            raise SPSDKError("Program operation requires 4 or 8 byte segment")

        # swap byte order
        data_word1 = swap32(data_word1)
        data_word2 = swap32(data_word2)

    # values provided as integer e.g. 0x1000 represents data_word1
    elif cmd_args.get("pattern"):
        int_value = cmd_args["pattern"]
        byte_count = get_bytes_cnt_of_int(int_value)

        if byte_count <= 4:
            data_word1 = int_value
        else:
            raise SPSDKError("Data word 1 must be 4 bytes long")
    else:
        raise SPSDKError("Unsupported program command arguments")

    return CmdProg(address=address, data_word1=data_word1, data_word2=data_word2, mem_id=mem_id)


def _erase_cmd_handler(cmd_args: dict) -> CmdErase:
    """Returns a CmdErase object initialized based on cmd_args.

    :param cmd_args: dictionary holding path to address, length and flags
    :return: CmdErase object
    """
    address = cmd_args["address"]
    length = cmd_args.get("length", 0)
    flags = cmd_args.get("flags", 0)

    mem_opt = cmd_args.get("mem_opt")
    mem_id = 0
    if mem_opt:
        mem_id = get_mem_id(mem_opt)

    return CmdErase(address=address, length=length, flags=flags, mem_id=mem_id)


def _enable(cmd_args: dict) -> CmdMemEnable:
    """Returns a CmdEnable object initialized based on cmd_args.

    :param cmd_args: dictionary holding address, size and memory type
    :return: CmdEnable object
    """
    address = cmd_args["address"]
    size = cmd_args.get("size", 4)
    mem_opt = cmd_args.get("mem_opt")
    mem_id = 0
    if mem_opt:
        mem_id = get_mem_id(mem_opt)
    return CmdMemEnable(address=address, size=size, mem_id=mem_id)


def _encrypt(cmd_args: dict) -> CmdLoad:
    """Returns a CmdLoad object initialized based on cmd_args.

    Encrypt holds an ID, which is a reference to keyblob to be used for
    encryption. So the encrypt command requires a list of keyblobs, the keyblob
    ID and load command.

    e.g.
    encrypt (0){
        load myImage > 0x0810000;
    }

    :param cmd_args: dictionary holding list of keyblobs, keyblob ID and load dict
    :raises SPSDKError: If keyblob to be used is not in the list or is invalid
    :return: CmdLoad object
    """
    keyblob_id = cmd_args["keyblob_id"]
    keyblobs = cmd_args.get("keyblobs", [])
    load_dict = cmd_args.get("load", {})

    address = load_dict["address"]

    if load_dict.get("file"):
        data = load_binary(load_dict["file"])
    if load_dict.get("values"):
        values = [int(s, 16) for s in load_dict["values"].split(",")]
        data = struct.pack(f"<{len(values)}L", *values)

    try:
        valid_keyblob = _validate_keyblob(keyblobs, keyblob_id)
    except SPSDKError as exc:
        raise SPSDKError(f"Invalid key blob {str(exc)}") from exc

    if valid_keyblob is None:
        raise SPSDKError(f"Missing keyblob {keyblob_id} for encryption.")

    start_addr = valid_keyblob["keyblob_content"][0]["start"]
    end_addr = valid_keyblob["keyblob_content"][0]["end"]
    key = bytes.fromhex(valid_keyblob["keyblob_content"][0]["key"])
    counter = bytes.fromhex(valid_keyblob["keyblob_content"][0]["counter"])
    byte_swap = valid_keyblob["keyblob_content"][0].get("byte_swap", False)

    keyblob = KeyBlob(start_addr=start_addr, end_addr=end_addr, key=key, counter_iv=counter)

    # Encrypt only if the ADE and VLD flags are set
    if bool(end_addr & keyblob.KEY_FLAG_ADE) and bool(end_addr & keyblob.KEY_FLAG_VLD):
        encoded_data = keyblob.encrypt_image(
            base_address=address, data=align_block(data, 512), byte_swap=byte_swap
        )
    else:
        encoded_data = data

    return CmdLoad(address, encoded_data)


def _keywrap(cmd_args: dict) -> CmdLoad:
    """Returns a CmdLoad object initialized based on cmd_args.

    Keywrap holds keyblob ID to be encoded by a value stored in load command and
    stored to address defined in the load command.

    e.g.
    keywrap (0) {
        load {{ 00000000 }} > 0x08000000;
    }

    :param cmd_args: dictionary holding list of keyblobs, keyblob ID and load dict
    :raises SPSDKError: If keyblob to be used is not in the list or is invalid
    :return: CmdLoad object
    """
    # iterate over keyblobs
    keyblobs = cmd_args.get("keyblobs", None)
    keyblob_id = cmd_args.get("keyblob_id", None)
    load_info = cmd_args.get("load", None)

    address = load_info.get("address")
    otfad_key = load_info.get("values")

    try:
        valid_keyblob = _validate_keyblob(keyblobs, keyblob_id)
    except SPSDKError as exc:
        raise SPSDKError(f" Key blob validation failed: {str(exc)}") from exc
    if valid_keyblob is None:
        raise SPSDKError(f"Missing keyblob {keyblob_id} for given keywrap")

    start_addr = valid_keyblob["keyblob_content"][0]["start"]
    end_addr = valid_keyblob["keyblob_content"][0]["end"]
    key = bytes.fromhex(valid_keyblob["keyblob_content"][0]["key"])
    counter = bytes.fromhex(valid_keyblob["keyblob_content"][0]["counter"])

    blob = KeyBlob(start_addr=start_addr, end_addr=end_addr, key=key, counter_iv=counter)

    encoded_keyblob = blob.export(kek=otfad_key)
    print("creating wrapped keyblob")

    return CmdLoad(address=address, data=encoded_keyblob)


def _keystore_to_nv(cmd_args: dict) -> CmdKeyStoreRestore:
    """Returns a CmdKeyStoreRestore object initialized with memory type and address.

    The keystore_to_nv statement instructs the bootloader to load the backed up
    keystore values back into keystore memory region on non-volatile memory.

    section (0) {
        keystore_to_nv @9 0x8000800;

    :param cmd_args: dictionary holding the memory type and address.
    :return: CmdKeyStoreRestore object.
    """
    mem_opt = cmd_args["mem_opt"]
    address = cmd_args["address"]
    return CmdKeyStoreRestore(address, mem_opt)


def _keystore_from_nv(cmd_args: dict) -> CmdKeyStoreBackup:
    """Returns a CmdKeyStoreRestore object initialized with memory type and address.

    The keystore_to_nv statement instructs the bootloader to load the backed up
    keystore values back into keystore memory region on non-volatile memory.

    section (0) {
        keystore_to_nv @9 0x8000800;

    :param cmd_args: dictionary holding the memory type and address.
    :return: CmdKeyStoreRestore object.
    """
    mem_opt = cmd_args["mem_opt"]
    address = cmd_args["address"]
    return CmdKeyStoreBackup(address, mem_opt)


def _version_check(cmd_args: dict) -> CmdVersionCheck:
    """Returns a CmdVersionCheck object initialized with version check type and version.

    Validates version of secure or non-secure firmware.
    The command fails if version is < expected.

    section (0) {
        version_check sec 0x2;
        version_check nsec 2;

    :param cmd_args: dictionary holding the version type and fw version.
    :return: CmdKeyStoreRestore object.
    """
    ver_type = cmd_args["ver_type"]
    fw_version = cmd_args["fw_version"]
    return CmdVersionCheck(ver_type, fw_version)


def _validate_keyblob(keyblobs: List, keyblob_id: Number) -> Optional[Dict]:
    """Checks, whether a keyblob is valid.

    Parser returns a list of dicts which contains keyblob definitions. These
    definitions should contain a 'start', 'end', 'key' & 'counter' keys with
    appropriate values. To be able to create a keyblob, we need these for
    values. Otherwise we throw an exception that the keyblob is invalid.

    :param keyblobs: list of dicts defining keyblobs
    :param keyblob_id: id of keyblob we want to check
    :raises SPSDKError: If the keyblob definition is empty
    :raises SPSDKError: If the keyblob definition is missing one key
    :return: keyblob If exists and is valid, None otherwise
    """
    for keyblob in keyblobs:
        if keyblob_id == keyblob["keyblob_id"]:
            kb_content = keyblob["keyblob_content"]
            if len(kb_content) == 0:
                raise SPSDKError(f"Keyblob {keyblob_id} definition is empty!")

            for key in ["start", "end", "key", "counter"]:
                if key not in kb_content[0]:
                    raise SPSDKError(f"Keyblob {keyblob_id} is missing '{key}' definition!")

            return keyblob

    return None


def _jump(cmd_args: dict) -> CmdJump:
    """Returns a CmdJump object initialized with memory type and address.

    The "jump" command produces the ROM_JUMP_CMD.
    See the boot image format design document for specific details about these commands,
    such as the function prototypes they expect.

    section (0) {
        # jump to the entrypoint
        jump mySRecFile;
        # jump to a fixed address
        jump 0xffff0000;
    }

    :param cmd_args: dictionary holding the argument and address.
    :return: CmdJump object.
    """
    argument = cmd_args.get("argument", 0)
    address = cmd_args["address"]
    spreg = cmd_args.get("spreg")

    return CmdJump(address, argument, spreg)


cmds = {
    "load": _load,
    "fill": _fill_memory,
    "erase": _erase_cmd_handler,
    "enable": _enable,
    "encrypt": _encrypt,
    "keywrap": _keywrap,
    "keystore_to_nv": _keystore_to_nv,
    "keystore_from_nv": _keystore_from_nv,
    "version_check": _version_check,
    "jump": _jump,
}