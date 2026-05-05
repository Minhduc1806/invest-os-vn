# Tool Spec: fdata_proto_decoder

## Purpose
Decode đầy đủ metadata từ FData `Common/symbols.dat` và `Common/symbolInfo.dat`, thay cho parser partial.

## Implemented File
```text
scripts/fdata_proto_tool.py
```

## Inputs
```text
C:\Users\DUC\Documents\FDATA\Common\symbols.dat
C:\Users\DUC\Documents\FDATA\Common\symbolInfo.dat
C:\Users\DUC\Documents\FDATA\Common\ICBs.dat
C:\Users\DUC\Documents\FDATA\Common\types.dat
```

## Outputs
```text
data_live/fdata_symbols_full.json
data_live/fdata_proto_fieldmap.json
data_live/fdata_sector_candidates.json
```

## Command
```bash
python scripts/fdata_proto_tool.py --sample FPT,MWG,VCB,SSI
```

## Current Capabilities
- Decode `symbols.dat` record format directly.
- Extract ticker, name, exchange, type, code, raw offset.
- Enrich URL/company_name from `symbolInfo.dat`.
- Generate fieldmap to reverse-engineer unknown protobuf fields.
- Generate sector_candidates for later ngành mapping.

## Verified Sample
- FPT: HSX, stock, Công ty Cổ phần FPT.
- MWG: HSX, stock, Công ty Cổ phần Đầu tư Thế Giới Di Động.
- VCB: HSX, stock, Ngân hàng Thương mại Cổ phần Ngoại Thương Việt Nam.
- SSI: HSX, stock, Công ty Cổ phần Chứng khoán SSI.

## Remaining Work
- Decode exact industry/ICB link from `symbolInfo.dat` or `ICBs.dat`.
- Clean leading protobuf length chars in `company_name` fallback.
- Join metadata into `fdata_adapter.py` bars.

## Failure Modes
- `schema_changed`: FData changes binary layout.
- `unicode_decode_partial`: non-UTF8 bytes near text fields.
- `industry_missing`: sector/ICB not decoded yet.
