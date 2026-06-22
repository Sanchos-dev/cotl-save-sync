const fs = require('fs');
const path = require('path');
const msgpack = require('@msgpack/msgpack');
const lz4 = require('@addmaple/lz4/inline');
const crypto = require('crypto');
const AdmZip = require('adm-zip');

// Portable Paths based on script directory
const CULT_SYNC_DIR = __dirname;
const TEMP_DIR = path.join(CULT_SYNC_DIR, "temp_extracted");
const PC_VERSION = "1.5.25.1049";
const SWITCH_VERSION = "1.5.24";
const PC_SAVES_DIR = path.join(process.env.USERPROFILE, 'AppData', 'LocalLow', 'Massive Monster', 'Cult Of The Lamb', 'saves');

// Helper to decrypt AES-128-CBC save file
function decryptSave(filePath) {
    const data = fs.readFileSync(filePath);
    if (data[0] !== 0x45) throw new Error("File is not encrypted with 'E' prefix!");
    const key = data.slice(1, 17);
    const iv = data.slice(17, 33);
    const ciphertext = data.slice(33);
    
    const decipher = crypto.createDecipheriv('aes-128-cbc', key, iv);
    decipher.setAutoPadding(false);
    let decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
    
    // PKCS7 unpadding
    const padLen = decrypted[decrypted.length - 1];
    if (padLen > 0 && padLen <= 16) {
        decrypted = decrypted.slice(0, -padLen);
    }
    return decrypted;
}

// Helper to decompress and decode Switch save or metadata
async function decodeCompressedMP(buffer) {
    if (buffer.slice(0, 2).toString() === "MP") {
        buffer = buffer.slice(2);
    }
    
    // Decode outer MessagePack (array of blocks)
    const outer = msgpack.decode(buffer);
    if (outer[0] && outer[0].type === 98) {
        const compressedHeader = outer[0];
        const headerGenerator = msgpack.decodeMulti(compressedHeader.data);
        const header = Array.from(headerGenerator);
        
        const compressedBody = outer.slice(1);
        const decompressedBody = [];
        for (let i = 0; i < compressedBody.length; i++) {
            const decompressed = await lz4.decompressBlock(compressedBody[i], header[i]);
            decompressedBody.push(decompressed);
        }
        
        const totalLength = decompressedBody.reduce((acc, curr) => acc + curr.length, 0);
        const combined = new Uint8Array(totalLength);
        let offset = 0;
        for (const block of decompressedBody) {
            combined.set(block, offset);
            offset += block.length;
        }
        
        return msgpack.decode(combined);
    } else {
        return outer;
    }
}

// Compress a flat array to the block compressed format
async function encodeCompressedMP(flatArray) {
    const encodedFlat = msgpack.encode(flatArray);
    
    // Chunk into 32KB blocks
    const blockSize = 32768;
    const blocks = [];
    const lengths = [];
    for (let o = 0; o < encodedFlat.length; o += blockSize) {
        const chunk = encodedFlat.slice(o, o + blockSize);
        blocks.push(chunk);
        lengths.push(chunk.length);
    }
    
    // Compress blocks using lz4
    const compressedBlocks = [];
    for (let i = 0; i < blocks.length; i++) {
        const compressed = await lz4.compressBlock(blocks[i]);
        compressedBlocks.push(compressed);
    }
    
    // Construct header
    const headerBytes = Buffer.concat(lengths.map(len => msgpack.encode(len)));
    const newHeader = new msgpack.ExtData(98, headerBytes);
    
    // Assemble outer array and encode
    const outerArray = [newHeader, ...compressedBlocks];
    return msgpack.encode(outerArray);
}

// Switch -> PC Sync Logic
async function runSwitchToPc() {
    console.log("=== RUNNING SWITCH -> PC CONVERSION ===");
    
    const slots = [
        { switchFile: "slot_0MP", isSlot: true },
        { switchFile: "slot_10MP", isSlot: true },
        { switchFile: "meta_0MP", isSlot: false },
        { switchFile: "meta_10MP", isSlot: false }
    ];
    
    for (const fileObj of slots) {
        const switchPath = path.join(TEMP_DIR, fileObj.switchFile);
        if (!fs.existsSync(switchPath)) {
            console.log(`[Warning] Switch file ${fileObj.switchFile} not found in temp_extracted.`);
            continue;
        }
        
        console.log(`Processing ${fileObj.switchFile}...`);
        try {
            const buffer = fs.readFileSync(switchPath);
            const flatArray = await decodeCompressedMP(buffer);
            
            let finalBytes;
            if (fileObj.isSlot) {
                // Patch TwitchSettings to PC array and append the 1396th element
                flatArray[325] = [null, true, 20, true, true, true];
                flatArray[322] = [];
                flatArray[324] = false;
                flatArray[328] = [];
                flatArray[329] = [];
                
                if (flatArray.length === 1395) {
                    flatArray.push([]);
                }
                console.log(`  Patched slot array size: ${flatArray.length}`);
                
                // slots MUST be compressed on PC
                finalBytes = await encodeCompressedMP(flatArray);
            } else {
                // Patch metadata version
                flatMeta = flatArray;
                flatMeta[29] = PC_VERSION;
                console.log(`  Updated metadata version to ${PC_VERSION}`);
                // metadata MUST be uncompressed flat MessagePack on PC
                finalBytes = msgpack.encode(flatMeta);
            }
            
            const outPath = path.join(CULT_SYNC_DIR, fileObj.switchFile + "_patched.bin");
            fs.writeFileSync(outPath, finalBytes);
            console.log(`  Saved patched binary to ${outPath} (${finalBytes.length} bytes)`);
            
        } catch (e) {
            console.error(`  Error processing ${fileObj.switchFile}:`, e);
        }
    }
}

// PC -> Switch Sync Logic
async function runPcToSwitch() {
    console.log("=== RUNNING PC -> SWITCH CONVERSION ===");
    
    // Find the latest original Switch backup zip file in CULT_SYNC
    const files = fs.readdirSync(CULT_SYNC_DIR);
    const zips = files.filter(f => f.startsWith("sanchos - ") && f.endsWith(".zip"));
    if (zips.length === 0) {
        throw new Error("No original Switch JKSV backup found in sync directory! We need it as a base to copy the .nx_save_meta.bin and other console metafiles.");
    }
    zips.sort();
    const latestSwitchZip = zips[zips.length - 1];
    console.log(`Using original Switch backup zip as base: ${latestSwitchZip}`);
    
    const baseZipPath = path.join(CULT_SYNC_DIR, latestSwitchZip);
    
    // Create copy of the base zip with the new sync name
    const timestamp = new Date().toISOString().replace(/T/, ' ').replace(/\..+/, '').replace(/:/g, '-').replace(' ', '_');
    const zipFileName = `sync_PC - ${timestamp}.zip`;
    const targetZipPath = path.join(CULT_SYNC_DIR, zipFileName);
    
    fs.copyFileSync(baseZipPath, targetZipPath);
    console.log(`Created target ZIP copy: ${zipFileName}`);
    
    // Open the target zip
    const zip = new AdmZip(targetZipPath);
    
    const slots = [
        { pcFile: "slot_0.mp", switchName: "slot_0MP", isSlot: true },
        { pcFile: "slot_10.mp", switchName: "slot_10MP", isSlot: true },
        { pcFile: "meta_0.mp", switchName: "meta_0MP", isSlot: false },
        { pcFile: "meta_10.mp", switchName: "meta_10MP", isSlot: false }
    ];
    
    let filesProcessedCount = 0;
    
    for (const fileObj of slots) {
        const pcFilePath = path.join(PC_SAVES_DIR, fileObj.pcFile);
        if (!fs.existsSync(pcFilePath)) {
            console.log(`[Warning] PC file ${fileObj.pcFile} not found in saves folder.`);
            continue;
        }
        
        console.log(`Processing ${fileObj.pcFile}...`);
        try {
            // 1. Decrypt PC Save File
            const decrypted = decryptSave(pcFilePath);
            
            // 2. Decode to Flat Array
            const flatArray = await decodeCompressedMP(decrypted);
            
            let finalBytes;
            if (fileObj.isSlot) {
                // Patch TwitchSettings to null
                flatArray[325] = null;
                flatArray[322] = [];
                flatArray[324] = false;
                flatArray[328] = [];
                flatArray[329] = [];
                
                // Pop the extra 1396th element to match Switch size of 1395
                if (flatArray.length === 1396) {
                    flatArray.pop();
                }
                console.log(`  Patched slot array size: ${flatArray.length}`);
                
                // Re-compress using LZ4
                const compressedBytes = await encodeCompressedMP(flatArray);
                
                // Prepend platform-specific Switch header "MP"
                finalBytes = Buffer.concat([Buffer.from('MP'), compressedBytes]);
            } else {
                // Patch metadata version
                flatMeta = flatArray;
                flatMeta[29] = SWITCH_VERSION;
                console.log(`  Updated metadata version to ${SWITCH_VERSION}`);
                
                // Switch expects compressed metadata
                const compressedMetaBytes = await encodeCompressedMP(flatMeta);
                
                // Prepend platform-specific Switch header "MP"
                finalBytes = Buffer.concat([Buffer.from('MP'), compressedMetaBytes]);
            }
            
            // Overwrite file inside the copy ZIP
            try {
                zip.deleteFile(fileObj.switchName);
            } catch (err) {}
            zip.addFile(fileObj.switchName, finalBytes);
            console.log(`  Updated Switch-compatible binary in ZIP: ${fileObj.switchName} (${finalBytes.length} bytes)`);
            filesProcessedCount++;
            
        } catch (e) {
            console.error(`  Error processing ${fileObj.pcFile}:`, e);
        }
    }
    
    // Process PC persistence
    const pcPersistencePath = path.join(PC_SAVES_DIR, "persistence");
    if (fs.existsSync(pcPersistencePath)) {
        console.log("Processing persistence...");
        try {
            const decryptedPersistence = decryptSave(pcPersistencePath);
            try {
                zip.deleteFile("persistence");
            } catch (err) {}
            zip.addFile("persistence", decryptedPersistence);
            console.log(`  Updated Switch-compatible persistence in ZIP (${decryptedPersistence.length} bytes)`);
            filesProcessedCount++;
        } catch (e) {
            console.error("  Error processing persistence:", e);
        }
    }
    
    if (filesProcessedCount > 0) {
        // Write the updated ZIP
        zip.writeZip(targetZipPath);
        console.log(`\n[Success] Created Switch JKSV Backup: ${zipFileName}`);
        console.log(`ZIP_PATH:${targetZipPath}`);
    } else {
        fs.unlinkSync(targetZipPath);
        console.log("\n[Error] No PC files were processed, ZIP copy deleted.");
    }
}

async function main() {
    const mode = process.argv[2] || "s2p";
    if (mode === "p2s") {
        await runPcToSwitch();
    } else {
        await runSwitchToPc();
    }
}

main();
