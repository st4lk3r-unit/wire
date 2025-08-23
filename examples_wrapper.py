#!/usr/bin/env python3
import argparse, os, sys, time, struct, zlib, serial, re

# ----- constants (fix TX_HDR) -----
MAGIC_HS = b"HS20"
MAGIC_TX = b"WRP2"
VER      = 2

HS_HDR = "<4sBHQI"   # HS20, ver(1), name_len(2), total_len(8), file_crc32(4)
TX_HDR = "<4sBQI"    # WRP2, ver(1), total_len(8), file_crc32(4)
BLK_HDR = "<HH"
ACK = b"K"
NAK = b"N"
FOK = b"OK"
FNO = b"NO"

# Console lines to wait for
CONFIRM_SEND = "Entering SEND mode"
CONFIRM_RECV = "Entering RECEIVE mode"

# For syncing to the console prompt if needed
ANSI_RE   = re.compile(rb"\x1B\[[0-9;?]*[ -/]*[@-~]")
PROMPT_RE = re.compile(rb"(^|\r?\n)#\s")

# ===== Helpers =====
def human(n):
    for u in ("","K","M","G","T"):
        if n < 1024.0: return f"{n:.1f}{u}B"
        n /= 1024.0
    return f"{n:.1f}P"

def open_port(port, baud, timeout=0.2, write_timeout=2.0, verbose=False):
    if verbose: print(f"[dbg] Opening {port} @ {baud} (avoid reset)…")
    ser = serial.serial_for_url(
        port, do_not_open=True,
        baudrate=baud, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout, write_timeout=write_timeout,
        rtscts=False, dsrdtr=False, xonxoff=False
    )
    # Keep control lines steady to minimize auto-reset
    ser.dtr = False
    ser.rts = False
    ser.open()
    if verbose: print(f"[dbg] Port open. DTR={ser.dtr} RTS={ser.rts}")
    return ser

def _strip_ansi(b: bytes) -> bytes: return ANSI_RE.sub(b"", b)
def _read_some(ser): return ser.read(ser.in_waiting or 1)

def read_until_prompt(ser, max_wait=2.0):
    deadline = time.time() + max_wait
    buf = bytearray()
    while time.time() < deadline:
        b = _read_some(ser)
        if b:
            buf += b
            if PROMPT_RE.search(_strip_ansi(bytes(buf))):
                return True
        else:
            ser.write(b"\r\n"); ser.flush()
            time.sleep(0.05)
    return False

def sync_on_magic(ser, magic: bytes, max_wait=30.0):
    """Slide a window until MAGIC appears or timeout."""
    deadline = time.time() + max_wait
    win = bytearray()
    m = len(magic)
    while time.time() < deadline:
        b = ser.read(1)
        if not b:
            continue
        win += b
        if len(win) > m:
            del win[0:len(win)-m]
        if len(win) == m and bytes(win) == magic:
            return True
    return False

def wait_for_ack_byte(ser, ok=ACK, bad=NAK, timeout=5.0, verbose=False):
    """Consume bytes until we see 'ok' or 'bad', or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        b = ser.read(1)
        if not b:
            continue
        if b == ok:
            if verbose: print("[dbg] Got ACK")
            return True
        if b == bad:
            if verbose: print("[dbg] Got NAK")
            return False
        # Ignore any other noise (e.g., CR/LF from console)
    return False

def try_sync_prompt(ser, verbose=False):
    ser.reset_input_buffer()
    if read_until_prompt(ser, 1.5):
        if verbose: print("[dbg] Prompt detected.")
        return True
    ser.dtr = True; ser.rts = True
    if verbose: print("[dbg] Retrying with DTR/RTS True/True…")
    time.sleep(0.2)
    ser.reset_input_buffer()
    return read_until_prompt(ser, 1.5)

def wait_for_token(ser, token: str, max_wait=8.0):
    deadline = time.time() + max_wait
    buf = bytearray()
    needle = token.encode()
    while time.time() < deadline:
        b = _read_some(ser)
        if b:
            buf += b
            if needle in _strip_ansi(bytes(buf)):
                return True
        else:
            time.sleep(0.01)
    return False

def enter_mode(ser, mode: str, verbose=False):
    confirm = CONFIRM_SEND if mode == "send" else CONFIRM_RECV
    synced = try_sync_prompt(ser, verbose=verbose)
    if not synced and verbose:
        print("[dbg] No prompt seen — blind send of console command.")
    ser.reset_input_buffer()
    ser.write((mode + "\r\n").encode()); ser.flush()
    if not wait_for_token(ser, confirm, max_wait=8.0):
        sys.exit(f"[-] Did not see confirmation '{confirm}'. Adjust the firmware message or CONFIRM_* strings.")

def read_exact(ser, n) -> bytes:
    out = bytearray()
    while len(out) < n:
        b = ser.read(n - len(out))
        if not b: continue
        out.extend(b)
    return bytes(out)

def sender(port, usb_baud, file_path, block, retries, verbose=False):
    if not os.path.isfile(file_path):
        sys.exit(f"[-] File not found: {file_path}")

    total = os.path.getsize(file_path)
    file_crc = 0
    with open(file_path, "rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            file_crc = zlib.crc32(b, file_crc)
    file_crc &= 0xffffffff

    fname = os.path.basename(file_path)
    name_bytes = fname.encode("utf-8")
    if len(name_bytes) > 65535:
        sys.exit("[-] Filename too long for handshake (max 65535 bytes).")

    if verbose:
        print(f"[dbg] File={fname}, size={total}, file_crc=0x{file_crc:08x}, block={block} bytes")

    ser = open_port(port, usb_baud, verbose=verbose)
    try:
        # put ESP into SEND mode (your firmware prints 'Entering SEND mode')
        enter_mode(ser, "send", verbose=verbose)

        # purge any console leftovers before handshake
        ser.reset_input_buffer(); time.sleep(0.05); ser.reset_input_buffer()

        # ---- handshake: HS20 | ver | name_len | total | file_crc | name ----
        hs = struct.pack(HS_HDR, MAGIC_HS, VER, len(name_bytes), total, file_crc) + name_bytes
        if verbose: print(f"[dbg] Sending handshake ({len(hs)} bytes)")
        ser.write(hs); ser.flush()

        if not wait_for_ack_byte(ser, timeout=8.0, verbose=verbose):
            sys.exit("[-] Handshake not ACKed by receiver.")

        # ---- session header: WRP2 | ver | total | file_crc ----
        txh = struct.pack(TX_HDR, MAGIC_TX, VER, total, file_crc)
        if verbose: print(f"[dbg] Sending session header ({len(txh)} bytes)")
        ser.write(txh); ser.flush()

        # ---- stop-and-wait data blocks ----
        sent = 0; seq = 0; t0 = time.time()
        with open(file_path, "rb") as f:
            while sent < total:
                data = f.read(min(block, total - sent))
                if not data: break
                blen = len(data)
                bcrc = zlib.crc32(data) & 0xffffffff
                pkt = struct.pack(BLK_HDR, seq, blen) + data + struct.pack("<I", bcrc)

                # retransmit loop
                for attempt in range(1, retries+1):
                    ser.write(pkt); ser.flush()
                    ack = ser.read(1)
                    if ack == ACK:
                        if verbose: print(f"[dbg] seq={seq} len={blen} ACK")
                        break
                    if verbose: print(f"[dbg] seq={seq} len={blen} NAK/timeout (try {attempt})")
                else:
                    sys.exit(f"[-] Too many NAKs/timeouts on block seq={seq}")

                sent += blen
                seq = (seq + 1) & 0xFFFF
                if not verbose:
                    rate = sent / max(time.time()-t0,1e-6)
                    print(f"\r[+] Sent {human(sent)}/{human(total)} @ {human(rate)}/s", end="", flush=True)
        if not verbose: print()

        # ---- final status from receiver ----
        final = ser.read(2)
        if final != FOK:
            sys.exit("[-] Receiver reported final CRC failure.")
        print("[+] Transfer complete and verified by receiver.")
    finally:
        ser.close()
        
def receiver(port, usb_baud, out_dir_or_file, block, verbose=False):
    ser = open_port(port, usb_baud, verbose=verbose)
    try:
        # put ESP into RECEIVE mode (your firmware prints 'Entering RECEIVE mode')
        enter_mode(ser, "receive", verbose=verbose)

        # purge any console leftovers, then sync to HS20
        ser.reset_input_buffer(); time.sleep(0.05); ser.reset_input_buffer()
        if verbose: print("[dbg] Waiting for handshake magic HS20…")
        if not sync_on_magic(ser, MAGIC_HS, max_wait=30.0):
            sys.exit("[-] Timeout waiting for handshake magic (HS20).")

        # we already consumed MAGIC_HS; read the rest of HS header
        hs_rest_len = struct.calcsize(HS_HDR) - len(MAGIC_HS)
        hs_rest = read_exact(ser, hs_rest_len)
        magic, ver, name_len, total, file_crc = struct.unpack(HS_HDR, MAGIC_HS + hs_rest)
        if ver != VER:
            sys.exit(f"[-] Bad handshake version: got {ver}, expected {VER}")

        name = read_exact(ser, name_len).decode("utf-8", errors="replace")

        # ACK handshake so sender proceeds
        ser.write(ACK); ser.flush()

        # choose output path
        out_path = out_dir_or_file if not os.path.isdir(out_dir_or_file) else os.path.join(out_dir_or_file, name)
        tmp_path = out_path + ".part"
        if verbose:
            print(f"[dbg] Handshake OK: name={name!r}, total={total}, file_crc=0x{file_crc:08x}")
            print(f"[dbg] Writing to: {tmp_path}")

        # ---- session header (sync to WRP2, then parse) ----
        if not sync_on_magic(ser, MAGIC_TX, max_wait=5.0):
            sys.exit("[-] Timeout waiting for data session magic (WRP2).")
        tx_rest_len = struct.calcsize(TX_HDR) - len(MAGIC_TX)
        tx_rest = read_exact(ser, tx_rest_len)
        magic2, ver2, total2, file_crc2 = struct.unpack(TX_HDR, MAGIC_TX + tx_rest)
        if ver2 != VER or total2 != total or file_crc2 != file_crc:
            sys.exit("[-] Data session header mismatch.")

        # ---- receive stop-and-wait blocks ----
        rcvd = 0; expect_seq = 0; t0 = time.time()
        with open(tmp_path, "wb") as f:
            while rcvd < total:
                bh = read_exact(ser, struct.calcsize(BLK_HDR))
                seq, blen = struct.unpack(BLK_HDR, bh)
                data = read_exact(ser, blen)
                bcrc = struct.unpack("<I", read_exact(ser, 4))[0]

                ok = (seq == expect_seq) and ((zlib.crc32(data) & 0xffffffff) == bcrc)
                if ok:
                    f.write(data); rcvd += blen
                    ser.write(ACK)
                    expect_seq = (expect_seq + 1) & 0xFFFF
                    if not verbose:
                        rate = rcvd / max(time.time()-t0,1e-6)
                        print(f"\r[+] Received {human(rcvd)}/{human(total)} @ {human(rate)}/s", end="", flush=True)
                else:
                    ser.write(NAK)
                    if verbose:
                        print(f"[dbg] NAK: seq={seq} (expect {expect_seq}) or bad block CRC (0x{bcrc:08x})")
        if not verbose: print()

        # ---- final whole-file CRC ----
        d = open(tmp_path, "rb").read()
        final = zlib.crc32(d) & 0xffffffff
        print(f"[+] Final CRC local=0x{final:08x}, expected=0x{file_crc:08x}")
        if final == file_crc:
            if os.path.exists(out_path): os.remove(out_path)
            os.rename(tmp_path, out_path)
            ser.write(FOK); ser.flush()
            print(f"[+] Saved to {out_path}")
        else:
            ser.write(FNO); ser.flush()
            print("[-] Final CRC mismatch. Keeping .part", file=sys.stderr)
    finally:
        ser.close()

# ===== CLI =====
def main():
    ap = argparse.ArgumentParser(description="ESP UART reliable transfer (handshake + per-block ACK/CRC + final verify)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--send", action="store_true", help="Enter ESP 'send' mode and transmit file")
    mode.add_argument("--receive", action="store_true", help="Enter ESP 'receive' mode and save file")
    ap.add_argument("--port", required=True, help="ESP USB serial (e.g., /dev/ttyUSB0 or COM7)")
    ap.add_argument("--usb-baud", type=int, default=115200, help="ESP USB console baud (Serial.begin)")
    ap.add_argument("--block", type=int, default=16384, help="Block size (default 16 KiB)")
    ap.add_argument("--retries", type=int, default=6, help="Max retransmits per block (sender)")
    ap.add_argument("--file", help="File to send (with --send)")
    ap.add_argument("--output", help="Output path or directory (with --receive)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.send and not args.file:
        ap.error("--send requires --file")
    if args.receive and not args.output:
        ap.error("--receive requires --output")

    try:
        if args.send:
            sender(args.port, args.usb_baud, args.file, args.block, args.retries, verbose=args.verbose)
        else:
            receiver(args.port, args.usb_baud, args.output, args.block, verbose=args.verbose)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user."); sys.exit(130)

if __name__ == "__main__":
    main()
