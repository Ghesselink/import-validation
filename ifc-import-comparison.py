from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import ifcopenshell
from ifcopenshell.file import file as IfcFile
from ifcopenshell.entity_instance import entity_instance as IfcEntity

import element

class Component(ABC):
    def __init__(self, entity_instance : ifcopenshell.entity_instance, name : str, parent : Optional['Component'] = None):
        self.entity_instance: ifcopenshell.entity_instance = entity_instance
        self.name: str = name
        self.parent: Optional['Component'] = parent
        self.entity_name: Optional[str] = self.calculate_entity_name()
        self.guid: Optional[str] = self.calculate_guid()
        self.entity_type: str = self.calculate_type()
        self.psets: List[PropertySet] = self._init_psets()
        
    def calculate_entity_name(self) -> Optional[str]:
        return self.entity_instance.Name if hasattr(self.entity_instance, 'Name') else None

    def calculate_guid(self) -> Optional[str]:
        return self.entity_instance.GlobalId if hasattr(self.entity_instance, 'GlobalId') else None

    def calculate_type(self) -> str:
        return self.entity_instance.is_a()
    
    def _init_psets(self):
        psets = []
        for relationship in getattr(self.entity_instance, 'IsDefinedBy', []):
            if relationship.is_a("IfcRelDefinesByProperties"):
                definition = relationship.RelatingPropertyDefinition
                if definition:
                    psets.append(PropertySet(entity_instance = definition,
                        name = 'PropertySet', 
                        parent=self))
        return psets
        

    def display(self) -> None:
        print(f"{self.__class__.__name__}: {self.entity_instance} ({self.guid})")

    def get_subcomponent_attributes(self):
        subcomponents = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, list):
                flattened_list = [item for sublist in attr for item in (sublist if isinstance(sublist, list) else [sublist])]
                if all(isinstance(item, Component) for item in flattened_list):
                    subcomponents.extend(flattened_list)
        return subcomponents
    
    def check_eq_import(self, other: 'Component', report: 'ComparisonReport') -> None:
        if self.guid != other.guid:
            report.add_deletion(self.guid, self.entity_type)
            report.add_addition(other.guid, self.entity_type)
            return

        if self.name != other.name:
            report.add_deletion(self.guid, self.entity_type)
            report.add_addition(self.guid, self.entity_type)

        for attr_name in dir(self):
            self_attr = getattr(self, attr_name)
            if isinstance(self_attr, list) and all(isinstance(item, Component) for item in self_attr):
                other_attr = getattr(other, attr_name, [])
                self._compare_subcomponents(self_attr, other_attr, report)

    def _compare_subcomponents(self, self_components, other_components, report):
        self_map = {comp.guid: comp for comp in self_components}
        other_map = {comp.guid: comp for comp in other_components}

        for guid, self_comp in self_map.items():
            if guid in other_map:
                self_comp.check_eq_import(other_map[guid], report)
            else:
                report.add_deletion(guid, self_comp.entity_type)

        for guid, other_comp in other_map.items():
            if guid not in self_map:
                report.add_addition(guid, other_comp.entity_type)



class Project(Component):
    """"
    #todo perhaps not the best to start the tree with the project
    Preference would be to have a single tree but file can contain multiple projects
    """
    def __init__(self, entity_instance, name, file):
        super().__init__(entity_instance, name)
        self.file = file
        self.sites: List[Site] = self._init_sites()

    def _init_sites(self):
        sites = []
        for decomposes in self.entity_instance.IsDecomposedBy or []:
            for related_object in decomposes.RelatedObjects:
                if related_object.is_a('IfcSite'):
                    sites.append(Site(entity_instance = related_object,
                                        name = 'Site', 
                                        parent=self))
        return sites


class Site(Component):
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.buildings : List[Building] = self._init_buildings()

    def _init_buildings(self):
        buildings = []
        decomposes = self.entity_instance.IsDecomposedBy or []
        for decomposition in decomposes:
            for related_object in decomposition.RelatedObjects:
                if related_object.is_a('IfcBuilding'):
                    buildings.append(Building(entity_instance = related_object,
                                                   name = 'Building', 
                                                   parent=self))
        return buildings
                    

    def display(self):
        print(f'Site: {self.entity_instance} ({self.guid})')
        for building in self.buildings:
            building.display()


class Building(Component):
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.storeys : List[Storey] = self._init_storeys()

    def _init_storeys(self):
        storeys = []
        decomposes = self.entity_instance.IsDecomposedBy or []
        for decomposes in decomposes:
            for related_object in decomposes.RelatedObjects:
                if related_object.is_a('IfcBuildingStorey'):
                    storeys.append(Storey(entity_instance = related_object,
                                               name = related_object.Name, parent=self))
        return storeys
        

    def display(self):
        print(f'Building: {self.entity_instance} ({self.guid}')
        for storeys in self.storeys:
            storeys.display()
        
    def get_storey_names(self):
        return [storey.name for storey in self.storeys]


class Storey(Component):
    ALLOWED_TYPES = ['IfcBeam', 'IfcColumn', 'IfcCovering', 'IfcDistributionElement', 'IfcDoor', 
                    'IfcMember', 'IfcObject', 'IfcOpening', 'IfcPipe', 'IfcRailing', 'IfcRoof',
                    'IfcSlab', 'IfcSpace', 'IfcStair', 'IfcWall', 'IfcWindow']
    
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.components : List[Component] = self._init_storey_elements()

    def _init_storey_elements(self):
        components = []
        contains_elements = self.entity_instance.ContainsElements or []
        for contains_element in contains_elements:
            for related_element in contains_element.RelatedElements:
                for comp_type in self.ALLOWED_TYPES:
                    if related_element.is_a(comp_type):
                        component_class = globals().get(comp_type, None)
                        if component_class:
                            component = component_class(entity_instance=related_element,
                                                        name=related_element.Name, 
                                                        parent=self)
                            components.append(component)
        return components



    def display(self):
        print(f"Storey: {self.entity_instance} ({self.guid}")


class IfcBeam(Component):
    pass

class IfcColumn(Component):
    pass

class IfcCovering(Component):
    pass

class IfcDistribution_Element(Component):
    pass

class IfcDoor(Component):
    pass

class IfcMember(Component):
        pass

class IfcObject(Component):
        pass

class IfcOpening(Component):
        pass

class IfcPipe(Component):
        pass

class IfcRailing(Component):
        pass

class IfcRoof(Component):
        pass

class IfcSlab(Component):
        pass

class IfcSpace(Component):
        pass

class IfcStair(Component):
        pass

class IfcWall(Component):
        pass

class IfcWindow(Component):
        pass


class PropertySet(Component):
    def __init__(self, entity_instance: ifcopenshell.entity_instance, name: str, parent: Optional['Component'] = None):
        super().__init__(entity_instance, name, parent)
        self.properties = self._init_properties()
    
    def _init_properties(self):
        pass


class ComparisonReport:
    def __init__(self):
        self.additions = []
        self.deletions = []

    def add_addition(self, guid, entity_type, msg = None):
        addition = {'guid' : guid, 'entity_type': entity_type}
        if msg is not None:
            addition['message'] = msg
        self.additions.append(addition)

    def add_deletion(self, guid, entity_type, msg = None):
        deletion = {'guid' : guid, 'entity_type': entity_type}
        if msg is not None:
            deletion['message'] = msg
        self.deletions.append(deletion)

    def add_modification(self, guid, entity_type, msg = None):
        """
        Modifications are in the style of 'git diff'; one element deleted and one added
        """
        self.add_deletion(guid, entity_type, msg)
        self.add_addition(guid, entity_type, msg)

    def display(self):
        for i in self.deletions:
            message = f" -> {i['message']}" if 'message' in i else ""
            print(f"\033[91mDeleted: {i['guid']} ({i['entity_type']}){message}\033[0m")
        for i in self.additions:
            message = f" -> {i['message']}" if 'message' in i else ""
            print(f"\033[92mAdded: {i['guid']} ({i['entity_type']}){message}\033[0m")


def get_properties(instance : ifcopenshell.entity_instance) -> Dict[str, Any]:
    def get_recursive_props(psets):
        properties = {}
        for name, value in psets.items():
            if isinstance(value, dict):
                properties[name] = get_recursive_props(value)
            else:
                properties[name] = value
        return properties
    return get_recursive_props(ifcopenshell.util.element.get_psets(instance))


def run(original_fn : str, import_fn : str) -> None:
    print(f"Validating import : {import_fn}")
    report = ComparisonReport()

    original_file = ifcopenshell.open(original_fn)
    original_tree = Project(original_file.by_type('IfcProject')[0], 'Project', original_file)

    import_file = ifcopenshell.open(import_fn)
    import_tree = Project(import_file.by_type('IfcProject')[0], 'Project', file = import_file)

    # wall = original_file.by_guid('1nOs6Hg0v9fR$sLR1LjIyX')
    # element.get_psets(wall, should_inherit=False)

    original_tree.check_eq_import(import_tree, report)

    report.display()

if __name__ == '__main__':
    run(original_fn = 'original_Schependomlaan (1).ifc', import_fn = 'test_files/3_schependomlaan.ifc')