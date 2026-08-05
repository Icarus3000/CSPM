# CSPM Template Discovery Checklist

This document provides a text-only governed discovery checklist for a future expert-assisted template preparation exercise. 
**Do not execute this preparation process alone or automatically.** The repository does not currently contain functional VBA payloads or governed test fixtures for templates.

A trusted technical reviewer must perform the following discovery steps on a separate, controlled copy of a known-good workbook, entirely independent of the live authoritative data (`data/CSPM.xlsm` and `data/Dockets.xlsm`).

## Technical Discovery Steps

The technical reviewer must manually inspect the known-good workbook using the Excel Developer Ribbon and VBA Project Editor to determine and document the following:

1.  **VBA Module Names**: List all standard modules, class modules, and userforms (e.g., `Module1`, `ClientWizard`).
2.  **Macro Entry Points**: Identify all publicly callable Subroutines and Functions (e.g., `Sub LaunchWizard()`).
3.  **Workbook Event Handlers**: Document any logic running on `Workbook_Open`, `Workbook_BeforeClose`, `Workbook_BeforeSave`, etc., in the `ThisWorkbook` module.
4.  **Worksheet Event Handlers**: Document any logic running on `Worksheet_Change`, `Worksheet_Calculate`, or `Worksheet_SelectionChange`.
5.  **Ribbon Callbacks**: If the workbook has a custom XML ribbon, list all `onAction` callback signatures and map them to their corresponding VBA subroutines.
6.  **Hidden and Very-Hidden Worksheets**: Identify any worksheets with `Visible = xlSheetHidden` or `xlSheetVeryHidden` that may store seed data, state, or configuration.
7.  **Named Ranges**: List all Workbook-scoped and Worksheet-scoped named ranges and their formulas/references (e.g., `Config_TaxRate = 0.13`).
8.  **External Links**: Identify any `.xlsm` or `.xlsx` links in the Edit Links dialog.
9.  **Connections / Queries**: Check Power Query or traditional Data Connections for external data sources.
10. **Formulas**: Review the standard calculation columns within structured tables.
11. **Table Schemas**: Map exact `ListObject` table names to their host worksheets (e.g., Table `TBL_MATTERS` on sheet `Matters`).
12. **Lookup Seed Data**: Identify dropdown validation lists or standard reference values located in hidden configuration sheets.
13. **Custom XML**: Check the custom XML parts via the Developer tab or ZIP structure for configuration schemas.
14. **Document Properties**: Check Custom Document Properties for metadata.
15. **Comments and Notes**: Review for cell notes containing operational instructions.
16. **Embedded Objects**: Look for embedded PDFs, OLE objects, or ActiveX controls.
17. **Pivot Caches**: Identify PivotTables and ensure their caches do not contain ghost data.
18. **Cached Sensitive Values**: Identify cells where calculation outputs might be hardcoded as values rather than formulas.
19. **Hardcoded Paths**: Search the VBA codebase for hardcoded `C:\` or `\\Server\` paths.
20. **Hardcoded Client Information**: Search for hardcoded names, PII, or financial values.
21. **Dependencies**: Determine exactly how `CSPM.xlsm` and `Dockets.xlsm` expect to link to each other or to external operational files.

Once the discovery process above is complete and the architecture is formally mapped, a targeted **Sanitization Checklist** can be created to scrub the known-good workbooks and produce the final, hashed, and approved release templates.
