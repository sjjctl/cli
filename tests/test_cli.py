# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 15:19:53 2020

@author: shane
"""
import os
import sqlite3
import sys

import pytest

from ntclient import (
    NTSQLITE_BUILDPATH,
    NUTRA_DIR,
    USDA_DB_NAME,
    __db_target_nt__,
    __db_target_usda__,
    set_flags,
)
from ntclient.__main__ import build_argparser
from ntclient.__main__ import main as nt_main
from ntclient.core import nutprogbar
from ntclient.ntsqlite.sql import build_ntsqlite
from ntclient.persistence.sql.nt import funcs as nt_funcs
from ntclient.persistence.sql.nt import nt_ver
from ntclient.persistence.sql.usda import funcs as usda_funcs
from ntclient.persistence.sql.usda import sql as _usda_sql
from ntclient.persistence.sql.usda import usda_ver
from ntclient.services import init
from ntclient.utils.exceptions import SqlInvalidVersionError

# TODO: integration tests.. create user, recipe, log.. analyze & compare
arg_parser = build_argparser()
TEST_HOME = os.path.dirname(os.path.abspath(__file__))


def test_000_init():
    """Tests the SQL/persistence init in real time"""
    code, result = init(yes=True)
    assert code == 0
    assert result


def test_100_usda_sql_funcs():
    """Performs cursory inspection (sanity checks) of usda.sqlite3 image"""
    version = usda_ver()
    assert version == __db_target_usda__
    result = usda_funcs.sql_nutrients_details()
    assert len(result[1]) == 186

    result = usda_funcs.sql_servings([9050, 9052])
    assert len(result) == 3

    result = usda_funcs.sql_analyze_foods([23567, 23293])
    assert len(result) == 188

    result = usda_funcs.sql_sort_foods(789)
    assert len(result) == 415
    # result = usda_funcs.sql_sort_foods(789, fdgrp_ids=[100])
    # assert len(result) == 1

    result = usda_funcs.sql_sort_foods_by_kcal(789)
    assert len(result) == 246
    # result = usda_funcs.sql_sort_foods_by_kcal(789, fdgrp_ids=[1100])
    # assert len(result) == 127


def test_200_nt_sql_funcs():
    """Performs cursory inspection (sanity check) of nt.sqlite3 image"""
    version = nt_ver()
    assert version == __db_target_nt__

    headers, rows = nt_funcs.sql_biometrics()
    assert headers == ["id", "name", "unit", "created"]
    assert len(rows) == 29


def test_300_argparser_debug_no_paging():
    """Verifies the debug and no_paging flags are set"""
    args = arg_parser.parse_args(args=["-d", "--no-pager"])
    set_flags(args)

    assert args.debug is True
    assert args.no_paging is True

    from ntclient import DEBUG, PAGING  # pylint: disable=import-outside-toplevel

    assert DEBUG is True
    assert PAGING is False


def test_400_usda_argparser_funcs():
    """Tests udsa functions in argparser.funcs (to varying degrees each)"""
    # Init
    args = arg_parser.parse_args(args=["init", "-y"])
    assert args.yes is True
    code, result = args.func(args=args)
    assert code == 0
    assert result

    # Nutrients ( and `--no-pager` flag)
    args = arg_parser.parse_args(args=["--no-pager", "nt"])
    set_flags(args)  # unnecessary due to already happening, but hey
    code, result = args.func()
    assert code == 0
    assert len(result) == 186

    # Search
    args = arg_parser.parse_args(args=["search", "grass", "beef"])
    code, result = args.func(args)
    assert code == 0
    assert result
    # Top 20 (beats injecting BUFFER_HT/DEFAULT_RESULT_LIMIT)
    args = arg_parser.parse_args(args=["search", "grass", "beef", "-t", "20"])
    code, result = args.func(args)
    assert code == 0
    assert len(result) == 20
    assert result[0]["long_desc"] is not None

    # Sort
    args = arg_parser.parse_args(args=["sort", "789"])
    code, result = args.func(args)
    assert code == 0
    assert result
    # Top 20
    args = arg_parser.parse_args(args=["sort", "789", "-t", "20"])
    code, result = args.func(args)
    assert code == 0
    assert len(result) == 20
    assert result[0][4] == "Capers, raw"

    # Anl
    args = arg_parser.parse_args(args=["anl", "9053"])
    code, nutrients_rows, servings_rows = args.func(args)
    assert code == 0
    assert len(nutrients_rows[0]) == 30
    assert len(servings_rows[0]) == 1

    # Day
    rda_csv_path = os.path.join(TEST_HOME, "resources", "rda", "dog-18lbs.csv")
    day_csv_path = os.path.join(TEST_HOME, "resources", "day", "dog.csv")
    args = arg_parser.parse_args(args=["day", "-r", rda_csv_path, day_csv_path])
    code, result = args.func(args)
    assert code == 0
    assert result[0][213] == 1.295
    assert len(result[0]) == 177


def test_401_invalid_path_day_throws_error():
    """Ensures invalid path throws exception in `day` subcommand"""
    invalid_day_csv_path = os.path.join(
        TEST_HOME, "resources", "day", "__NONEXISTENT_CSV_FILE__.csv"
    )
    with pytest.raises(SystemExit) as sys_exit:
        arg_parser.parse_args(args=["day", invalid_day_csv_path])
    assert sys_exit.value.code == 2

    invalid_rda_csv_path = os.path.join(
        TEST_HOME, "resources", "rda", "__NONEXISTENT_CSV_FILE__.csv"
    )
    with pytest.raises(SystemExit) as sys_exit:
        arg_parser.parse_args(
            args=["day", "-r", invalid_rda_csv_path, invalid_day_csv_path]
        )
    assert sys_exit.value.code == 2


def test_402_nt_argparser_funcs():
    """Tests nt functions in argparser.funcs (to varying degrees each)"""


def test_500_main_module():
    """Tests execution of main() and __main__, in __main__.py"""
    code = nt_main(args=["--no-pager", "nt"])
    assert code == 0

    sys.argv = ["./nutra"]
    code = nt_main()
    assert code == 1

    with pytest.raises(SystemExit) as system_exit:
        nt_main(args=["-h"])
    assert system_exit.value.code == 0

    # __main__: if args_dict
    code = nt_main(args=["anl", "9053", "-g", "80"])
    assert code == 0


def test_600_sql_integrity_error__service_wip():
    """Provokes IntegrityError in nt.sqlite3"""
    from ntclient.services import biometrics  # pylint: disable=import-outside-toplevel

    args = arg_parser.parse_args(args=["-d", "bio", "log", "add", "12,12"])
    biometrics.input = (
        lambda x: "y"
    )  # mocks input, could also pass `-y` flag or set yes=True

    with pytest.raises(sqlite3.IntegrityError) as integrity_error:
        args.func(args)
    assert (
        integrity_error.value.args[0]
        == "NOT NULL constraint failed: biometric_log.profile_id"
    )


def test_700_build_ntsqlite_succeeds():
    """Verifies the service level call for git submodule"""
    try:
        os.remove(NTSQLITE_BUILDPATH)
    except FileNotFoundError:
        pass
    assert not os.path.exists(NTSQLITE_BUILDPATH)

    result = build_ntsqlite(verbose=True)
    assert result is True
    assert os.path.isfile(NTSQLITE_BUILDPATH)
    os.remove(NTSQLITE_BUILDPATH)


def test_800_usda_upgrades_or_downgrades():
    """Ensures the static usda.sqlite3 file can be upgraded/downgraded as needed"""
    version = usda_ver()
    major, minor, release = version.split(".")
    new_release = str(int(release) + 1)
    new_version = ".".join([major, minor, new_release])
    _usda_sql(
        "INSERT INTO version (version) VALUES (?)",
        values=(new_version,),
        version_check=False,
    )

    code, successful = init(yes=True)
    assert code == 0
    assert successful is True


def test_801_sql_invalid_version_error_if_version_old():
    """Throws base custom SqlException...
    TODO: why lines still missing in `coverage` for __main__ ?"""
    _usda_sql(
        "DELETE FROM version WHERE version=?",
        values=(__db_target_usda__,),
        version_check=False,
    )

    with pytest.raises(SqlInvalidVersionError) as sql_invalid_version_error:
        nt_main(["-d", "nt"])
    assert sql_invalid_version_error is not None


def test_802_usda_downloads_fresh_if_missing_or_deleted():
    """Ensure download of usda.sqlite3.tar.xz, if usda.sqlite3 is missing"""
    from ntclient.persistence.sql import usda  # pylint: disable=import-outside-toplevel

    # TODO: similar for nt.sqlite3? Define development standards.. rebuilding, deleting, preserving
    #  remove whole `.nutra` in a special test?
    try:
        # TODO: export USDA_DB_PATH at package level, don't pepper os.path.join() throughout code?
        usda_path = os.path.join(NUTRA_DIR, USDA_DB_NAME)
        os.remove(usda_path)
    except (FileNotFoundError, PermissionError) as err:
        # TODO: resolve PermissionError on Windows
        print(repr(err))
        _usda_sql(
            "INSERT INTO version (version) VALUES (?)",
            values=(__db_target_usda__,),
            version_check=False,
        )
        pytest.xfail("PermissionError, are you using Microsoft Windows?")

    usda.input = lambda x: "y"  # mocks input, could also pass `-y` flag or set yes=True
    code, successful = init()
    assert code == 0
    assert successful is True


def test_900_nut_rda_bar():
    """Verifies colored/visual output is correctly generated"""
    analysis = usda_funcs.sql_analyze_foods(food_ids=[1001])
    nutrients = usda_funcs.sql_nutrients_overview()
    output = nutprogbar.nutprogbar(
        food_amts={1001: 100}, food_analyses=analysis, nutrients=nutrients
    )
    assert output