#!/usr/bin/env python3
"""壁 — 評価層を Landlock の中で起動する（Linux）。

    python3 lib/壁.py --書ける <dir> [--書ける <dir> ...] -- node 判定.mjs --壁の中 種/型15.jsonl

## なぜ要るか

門（lib/門.mjs）は解釈系（python・pytest・node）を通さない。事例の手も、作業場の中身も
モデルが書くので、そのまま走らせると**モデルの書いたコードを本人の権限で実行する**ことになる。
そのせいで、型15（テストに細工して通した成功）と「テストが通ったと言うが落ちている」は、
砂場では一度も再現できなかった（どちらも python を走らせないと起きない）。

門を緩めるのではなく、**評価層まるごとを壁の中に入れる**。壁の中でだけ、門は解釈系を通す。

## 何を断るか（カーネルが断る）

- 書き込み: --書ける で渡した場所（と /dev/null など）以外への作成・書き込み・削除・改名
- TCP の接続と待ち受け（Landlock ABI 4 以上）
- 読むことは断らない（読まれて困るものは、この機械の評価層の作業場には置かない）

guardrun ほどの壁ではない（別ユーザ・資源の上限・残党の始末は無い）。guardrun と同じカーネルの
仕組み（Landlock）で、**書き込みと外への接続だけ**を確実に止める最小の壁である。

## 黙って緩まない

Landlock が使えない・ABI が足りない・規則を掛けられないときは、**走らせずに終わる**（終了コード 3）。
壁が無いのに壁の中だと思って解釈系を通すのが、一番まずいので。
起動する子には EVAL_WALL=landlock-abi<N> を渡す。判定.mjs はそれを見たうえで、
自分でも書き込みと接続を試して、断られることを確かめてから解釈系を通す。
"""

import ctypes
import os
import sys

SYS_create_ruleset, SYS_add_rule, SYS_restrict_self = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1

# 書き込み側の権利（ABI 1〜）。読む・実行するは扱わない＝断らない
WRITE_FILE, REMOVE_DIR, REMOVE_FILE = 1 << 1, 1 << 4, 1 << 5
MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = (1 << i for i in range(6, 13))
REFER, TRUNCATE, IOCTL_DEV = 1 << 13, 1 << 14, 1 << 15   # ABI 2, 3, 5
NET_BIND_TCP, NET_CONNECT_TCP = 1 << 0, 1 << 1           # ABI 4


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


libc = ctypes.CDLL(None, use_errno=True)


def 止める(理由):
    print(f"壁.py: 壁を立てられないので走らせない: {理由}", file=sys.stderr)
    sys.exit(3)


def abi():
    r = libc.syscall(SYS_create_ruleset, None, ctypes.c_size_t(0), ctypes.c_uint32(LANDLOCK_CREATE_RULESET_VERSION))
    return r if r > 0 else 0


def 立てる(書ける):
    v = abi()
    if v < 1:
        止める("Landlock が使えない")
    fs = (WRITE_FILE | REMOVE_DIR | REMOVE_FILE | MAKE_CHAR | MAKE_DIR | MAKE_REG | MAKE_SOCK
          | MAKE_FIFO | MAKE_BLOCK | MAKE_SYM)
    if v >= 2:
        fs |= REFER
    if v >= 3:
        fs |= TRUNCATE
    if v >= 5:
        fs |= IOCTL_DEV
    net = (NET_BIND_TCP | NET_CONNECT_TCP) if v >= 4 else 0
    # ABI 6 以上は scoped の欄がある。古い ABI には短い構造体を渡す
    attr = RulesetAttr(fs, net, 0)
    size = ctypes.sizeof(RulesetAttr) if v >= 6 else (16 if v >= 4 else 8)
    fd = libc.syscall(SYS_create_ruleset, ctypes.byref(attr), ctypes.c_size_t(size), ctypes.c_uint32(0))
    if fd < 0:
        止める(f"規則の束を作れない: {os.strerror(ctypes.get_errno())}")
    for d in 書ける + ["/dev/null", "/dev/zero", "/dev/urandom", "/dev/tty"]:
        if not os.path.exists(d):
            continue
        pfd = os.open(d, os.O_PATH | os.O_CLOEXEC)
        allowed = fs if os.path.isdir(d) else (WRITE_FILE | (TRUNCATE if v >= 3 else 0) | (IOCTL_DEV if v >= 5 else 0))
        rule = PathBeneathAttr(allowed, pfd)
        if libc.syscall(SYS_add_rule, ctypes.c_int(fd), ctypes.c_int(LANDLOCK_RULE_PATH_BENEATH),
                        ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
            止める(f"{d} に規則を足せない: {os.strerror(ctypes.get_errno())}")
        os.close(pfd)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        止める("no_new_privs を立てられない")
    if libc.syscall(SYS_restrict_self, ctypes.c_int(fd), ctypes.c_uint32(0)) < 0:
        止める(f"restrict_self に失敗: {os.strerror(ctypes.get_errno())}")
    os.close(fd)
    return v, bool(net)


def main(argv):
    書ける, i = [], 0
    while i < len(argv) and argv[i] != "--":
        if argv[i] == "--書ける" and i + 1 < len(argv):
            書ける.append(os.path.realpath(argv[i + 1]))
            i += 2
        else:
            止める(f"知らない引数: {argv[i]}")
    命令 = argv[i + 1:]
    if not 命令 or not 書ける:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(3)
    # 本当の家は環境変数の HOME ではなくユーザー情報で見る（HOME は一時置き場に差し替えて起動するので）
    import pwd
    本当の家 = os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)
    for d in 書ける:
        if d == "/" or d == 本当の家 or 本当の家.startswith(d + os.sep):
            止める(f"{d} を書ける場所にすると壁にならない")
    v, 網 = 立てる(書ける)
    env = dict(os.environ, EVAL_WALL=f"landlock-abi{v}" + ("" if 網 else "-no-net"),
               EVAL_WALL_WRITABLE=os.pathsep.join(書ける))
    os.execvpe(命令[0], 命令, env)


if __name__ == "__main__":
    main(sys.argv[1:])
