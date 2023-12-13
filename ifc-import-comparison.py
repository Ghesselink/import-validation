from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import ifcopenshell
from ifcopenshell.file import file as IfcFile
from ifcopenshell.entity_instance import entity_instance as IfcEntity

def do_try(fn, default: Optional[Any] = None) -> Any:
    try:
        return fn()
    except:
        import traceback
        traceback.print_exc()
        return default


class IfcContext(ABC):
    """
    Abstract class for IFC context; common attributes and methods
    """
    def __init__(self, file_path: str):
        self.file: IfcFile = ifcopenshell.open(file_path)
        self.entities: List[IfcEntity] = []
        self.entity_types: Set[str] = set()
        self.entities_with_props: Dict[str, Dict[str, Any]] = {}
        self.calculate_entities()

    @abstractmethod
    def calculate_entities(self) -> None:
        pass

    def get_creation_date(self) -> str:
        owner_history = self.file.by_type('IfcOwnerHistory')
        if owner_history:
            time_stamp = owner_history[0].CreationDate
            return datetime.utcfromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
        return 'No creation date'

    def get_iso_timestamp(self) -> str:
        return self.file.wrapped_data.header.file_name.time_stamp

    def add_property_set(self, entity: IfcEntity) -> None:
        prop_set = self.get_property_set(entity)
        if prop_set:
            self.entities_with_props[entity.GlobalId] = {
                'type': entity.is_a(),
                'property_set': prop_set
            }

    def get_property_set(self, entity: IfcEntity) -> Optional[Any]:
        if hasattr(entity, 'IsDefinedBy') and entity.IsDefinedBy:
            for definition in entity.IsDefinedBy:
                if definition.is_a('IfcRelDefinesByProperties'):
                    property_set = definition.RelatingPropertyDefinition
                    if property_set and property_set.is_a('IfcPropertySet'):
                        return property_set
            return None


class IfcOriginalContext(IfcContext):
    def calculate_entities(self):
        for entity in self.file:
            self.entities.append(entity)
            self.add_property_set(entity)
            self.entity_types.add(entity.is_a())


class IfcImportContext(IfcContext):
    def __init__(self, file_path:str, ifc_original_context : IfcOriginalContext):
        self.ifc_original_context = ifc_original_context
        self.report: Dict[str, Dict[str, Any]] = {}
        super().__init__(file_path)

    def calculate_entities(self):
        for t in self.ifc_original_context.entity_types:
            insts = self.file.by_type(t)
            if not insts:
                self.report[t] = {'expected': f'entity of type {t}', 'observed': None}
            else:
                self.entities.extend(insts)
                for inst in insts:
                    self.add_property_set(inst)
                self.entity_types.add(t)


def compare_entity_counts(ifc_original_context : IfcOriginalContext, ifc_import_context: IfcImportContext) -> None:
    """
    Compare entity counts between original and import context
    Modifies ifc_import_context.report
    """
    for t in ifc_import_context.entity_types:
        original_count = len(ifc_original_context.file.by_type(t))
        import_count = len(ifc_import_context.file.by_type(t))
        if original_count != import_count:
            ifc_import_context.report[t] = {'expected': f'{original_count} num of instances', 'observed': import_count}

def compare_entity_guids(ifc_original_context, ifc_import_context):
    """
    @todo restructure guidIds. Probably set context.entities to a dict with what as key?
    """
    # guid_ids_import = [entity.GlobalId for entity in entities_import]
    # guid_ids_export = [entity.GlobalId for entity in entities_export]

    # missing_guids = [guid for guid in guid_ids_export if guid not in guid_ids_import]
    # if len(missing_guids) > 0:
    #     print(f'guids not present in import: {len(missing_guids)}')
    pass

def compare_entity_timestamps(ifc_original_context: IfcOriginalContext, ifc_import_context: IfcImportContext) -> None:
    """
    Compare the creation dates and ISO timestamps between original and import contexts.
    Adds the timestamps to the respective context instances.
    """
    # Calculate and set timestamps for original context
    ifc_original_context.creation_date = ifc_original_context.get_creation_date()
    ifc_original_context.iso_timestamp = ifc_original_context.get_iso_timestamp()

    # Calculate and set timestamps for import context
    ifc_import_context.creation_date = ifc_import_context.get_creation_date()
    ifc_import_context.iso_timestamp = ifc_import_context.get_iso_timestamp()

    # Compare timestamps
    if ifc_original_context.creation_date != ifc_import_context.creation_date:
        ifc_import_context.report['creation_date'] = {
            'expected': ifc_original_context.creation_date, 
            'observed': ifc_import_context.creation_date
        }

    if ifc_original_context.iso_timestamp != ifc_import_context.iso_timestamp:
        ifc_import_context.report['iso_timestamp'] = {
            'expected': ifc_original_context.iso_timestamp, 
            'observed': ifc_import_context.iso_timestamp
        }


def run():
    original_path = '/Users/geerthesselink/Documents/BSI/Import-Certification/original_Schependomlaan (1).ifc'
    import_path = '/Users/geerthesselink/Documents/BSI/Import-Certification/import_Schependomlaan.ifc'

    ifc_original_context = IfcOriginalContext(original_path)
    ifc_import_context = IfcImportContext(import_path, ifc_original_context)

    compare_entity_counts(ifc_original_context, ifc_import_context)
    compare_entity_guids(ifc_original_context, ifc_import_context)
    compare_entity_timestamps(ifc_original_context, ifc_import_context)


if __name__ == '__main__':
    run()