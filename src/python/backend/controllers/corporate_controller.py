import logging
from typing import Any, Dict, List
import subprocess
import os

from PySide6.QtCore import QObject, Slot

from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo

logger = logging.getLogger(__name__)


class CorporateController(QObject):
    """
    Exposes corporate entity and transaction workflows to QML.
    Includes the Tapestry diagramming integration.
    """
    def __init__(self, repo: ExcelRepo, parent=None):
        super().__init__(parent)
        self._repo = repo

    @Slot(result="QVariantList")
    def listCorporateEntities(self) -> List[Dict[str, Any]]:
        try:
            return self._repo.list_corporate_entities()
        except Exception as e:
            logger.error(f"Failed to list corporate entities: {e}", exc_info=True)
            return []

    @Slot("QVariantMap", result="QVariantMap")
    def saveCorporateEntity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._repo.save_corporate_entity(payload)
        except Exception as e:
            logger.error(f"Failed to save corporate entity: {e}", exc_info=True)
            return {"ok": False, "message": str(e)}

    @Slot(result="QVariantList")
    def listCorporateRelationships(self) -> List[Dict[str, Any]]:
        try:
            return self._repo.list_corporate_relationships()
        except Exception as e:
            logger.error(f"Failed to list corporate relationships: {e}", exc_info=True)
            return []

    @Slot("QVariantMap", result="QVariantMap")
    def saveCorporateRelationship(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._repo.save_corporate_relationship(payload)
        except Exception as e:
            logger.error(f"Failed to save corporate relationship: {e}", exc_info=True)
            return {"ok": False, "message": str(e)}

    @Slot("QString", result="QVariantMap")
    def launchTapestryDiagram(self, client_name: str) -> Dict[str, Any]:
        """
        Exports corporate relationships for a client into a Tapestry-compatible CSV,
        then launches Tapestry pointing at that export directory.
        """
        tapestry_path = r"C:\Projects\__diag3"
        run_script = os.path.join(tapestry_path, "run.py")
        
        try:
            if not os.path.exists(run_script):
                return {"ok": False, "message": f"Tapestry run script not found at {run_script}"}

            # Gather data to export
            relationships = self.listCorporateRelationships()
            entities = self.listCorporateEntities()
            
            # Create a dictionary of entities by ID to look up names
            entity_map = {e.get(sc.COL_CORP_ENTITY_ID): e for e in entities}
            
            # Prepare export directory
            export_dir = os.path.join(self._repo.paths.data_dir(), "tapestry_export")
            os.makedirs(export_dir, exist_ok=True)
            
            # Build CSV
            # Tapestry columns: client_name,as_of_date,owner_name,owned_name,owner_type,owned_type,
            # share_count,share_class,ownership_kind,relationship_kind,debt_principal,debt_interest_rate,maturity_date,frozen_flag
            export_file = os.path.join(export_dir, f"{client_name or 'CSPM_Client'}_data.csv")
            
            with open(export_file, "w", encoding="utf-8") as f:
                f.write("client_name,as_of_date,owner_name,owned_name,owner_type,owned_type,share_count,share_class,ownership_kind,relationship_kind,debt_principal,debt_interest_rate,maturity_date,frozen_flag\n")
                
                # Write an empty line to initialize a node if there are no relationships
                if not relationships:
                    f.write(f"{client_name or 'CSPM_Client'},,,,,,0,,,,,,0\n")
                    
                for rel in relationships:
                    source_id = rel.get(sc.COL_CREL_SOURCE)
                    target_id = rel.get(sc.COL_CREL_TARGET)
                    
                    source_ent = entity_map.get(source_id, {})
                    target_ent = entity_map.get(target_id, {})
                    
                    owner_name = source_ent.get(sc.COL_CORP_LEGAL_NAME, source_id)
                    owned_name = target_ent.get(sc.COL_CORP_LEGAL_NAME, target_id)
                    
                    share_count = rel.get(sc.COL_CREL_SHARES_HELD, "")
                    share_class = rel.get(sc.COL_CREL_SHARE_CLASS, "")
                    
                    # Assuming basic ownership for now
                    f.write(f"{client_name or 'CSPM_Client'},,{owner_name},{owned_name},individual,corporation,{share_count},{share_class},Share ownership,ownership,,,,,0\n")
            
            env = os.environ.copy()
            env["DIAG3_DATA_DIR"] = export_dir
            
            # Launch Tapestry asynchronously so it doesn't block CSPM
            subprocess.Popen([sys.executable, "run.py"], cwd=tapestry_path, env=env)
            
            logger.info(f"Tapestry Launch requested with exported data for client: {client_name}")
            return {
                "ok": True, 
                "message": f"Tapestry launched successfully and synced data for {client_name}."
            }
        except Exception as e:
            logger.error(f"Failed to launch Tapestry: {e}", exc_info=True)
            return {"ok": False, "message": f"Failed to launch Tapestry: {e}"}
