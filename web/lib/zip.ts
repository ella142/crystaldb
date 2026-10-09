export interface ZipEntry {
  name: string;
  bytes: Uint8Array;
}

const CRC_TABLE = createCrcTable();
const LOCAL_FILE_SIGNATURE = 0x04034b50;
const CENTRAL_DIRECTORY_SIGNATURE = 0x02014b50;
const END_OF_CENTRAL_DIRECTORY_SIGNATURE = 0x06054b50;
const DOS_DATE_1980_01_01 = 33;

function createCrcTable(): Uint32Array {
  const table = new Uint32Array(256);
  for (let index = 0; index < table.length; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
}

function crc32(bytes: Uint8Array): number {
  let value = 0xffffffff;
  for (let index = 0; index < bytes.length; index += 1) {
    const byte = bytes[index];
    value = CRC_TABLE[(value ^ byte) & 0xff] ^ (value >>> 8);
  }
  return (value ^ 0xffffffff) >>> 0;
}

function writeUint16(target: Uint8Array, offset: number, value: number): void {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
}

function writeUint32(target: Uint8Array, offset: number, value: number): void {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  target[offset + 2] = (value >>> 16) & 0xff;
  target[offset + 3] = (value >>> 24) & 0xff;
}

function concatBytes(chunks: Uint8Array[], totalLength: number): Uint8Array {
  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

export function createZip(entries: ZipEntry[]): Uint8Array {
  const encoder = new TextEncoder();
  const localChunks: Uint8Array[] = [];
  const centralChunks: Uint8Array[] = [];
  const names = new Set<string>();
  let localOffset = 0;
  let localLength = 0;
  let centralLength = 0;

  for (const entry of entries) {
    if (!entry.name || names.has(entry.name)) {
      throw new Error(`ZIP entry names must be unique: ${entry.name || "empty name"}.`);
    }
    if (entry.name.includes("\\") || entry.name.startsWith("/")) {
      throw new Error(`ZIP entry name is not safe: ${entry.name}.`);
    }
    if (entry.bytes.length > 0xffffffff) {
      throw new Error(`ZIP entry is too large: ${entry.name}.`);
    }

    names.add(entry.name);
    const nameBytes = encoder.encode(entry.name);
    if (nameBytes.length > 0xffff) {
      throw new Error(`ZIP entry name is too long: ${entry.name}.`);
    }

    const checksum = crc32(entry.bytes);
    const localHeader = new Uint8Array(30 + nameBytes.length);
    writeUint32(localHeader, 0, LOCAL_FILE_SIGNATURE);
    writeUint16(localHeader, 4, 20);
    writeUint16(localHeader, 6, 0x0800);
    writeUint16(localHeader, 8, 0);
    writeUint16(localHeader, 10, 0);
    writeUint16(localHeader, 12, DOS_DATE_1980_01_01);
    writeUint32(localHeader, 14, checksum);
    writeUint32(localHeader, 18, entry.bytes.length);
    writeUint32(localHeader, 22, entry.bytes.length);
    writeUint16(localHeader, 26, nameBytes.length);
    writeUint16(localHeader, 28, 0);
    localHeader.set(nameBytes, 30);
    localChunks.push(localHeader, entry.bytes);
    localLength += localHeader.length + entry.bytes.length;

    const centralHeader = new Uint8Array(46 + nameBytes.length);
    writeUint32(centralHeader, 0, CENTRAL_DIRECTORY_SIGNATURE);
    writeUint16(centralHeader, 4, 20);
    writeUint16(centralHeader, 6, 20);
    writeUint16(centralHeader, 8, 0x0800);
    writeUint16(centralHeader, 10, 0);
    writeUint16(centralHeader, 12, 0);
    writeUint16(centralHeader, 14, DOS_DATE_1980_01_01);
    writeUint32(centralHeader, 16, checksum);
    writeUint32(centralHeader, 20, entry.bytes.length);
    writeUint32(centralHeader, 24, entry.bytes.length);
    writeUint16(centralHeader, 28, nameBytes.length);
    writeUint16(centralHeader, 30, 0);
    writeUint16(centralHeader, 32, 0);
    writeUint16(centralHeader, 34, 0);
    writeUint16(centralHeader, 36, 0);
    writeUint32(centralHeader, 38, 0);
    writeUint32(centralHeader, 42, localOffset);
    centralHeader.set(nameBytes, 46);
    centralChunks.push(centralHeader);
    centralLength += centralHeader.length;

    localOffset += localHeader.length + entry.bytes.length;
  }

  if (entries.length > 0xffff || localLength > 0xffffffff || centralLength > 0xffffffff) {
    throw new Error("ZIP archive is too large for the deterministic browser writer.");
  }

  const centralDirectoryOffset = localLength;
  const endRecord = new Uint8Array(22);
  writeUint32(endRecord, 0, END_OF_CENTRAL_DIRECTORY_SIGNATURE);
  writeUint16(endRecord, 4, 0);
  writeUint16(endRecord, 6, 0);
  writeUint16(endRecord, 8, entries.length);
  writeUint16(endRecord, 10, entries.length);
  writeUint32(endRecord, 12, centralLength);
  writeUint32(endRecord, 16, centralDirectoryOffset);
  writeUint16(endRecord, 20, 0);

  return concatBytes(
    [...localChunks, ...centralChunks, endRecord],
    localLength + centralLength + endRecord.length,
  );
}
