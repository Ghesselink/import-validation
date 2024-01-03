from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import ifcopenshell
from ifcopenshell.file import file as IfcFile
from ifcopenshell.entity_instance import entity_instance as IfcEntity
import pandas as pd


class Component(ABC):
    def __init__(self, entity_instance, name, parent = None):
        self.entity_instance = entity_instance
        self.name = name
        self.parent = parent
        self.entity_name = self.calculate_entity_name()
        self.guid = self.calculate_guid()
        self.entity_type = self.calculate_type()
        
    def calculate_entity_name(self):
        # Logic to extract name from entity
        return self.entity_instance.Name if hasattr(self.entity_instance, 'Name') else None

    def calculate_guid(self):
        # Logic to extract GUID from entity
        return self.entity_instance.GlobalId if hasattr(self.entity_instance, 'GlobalId') else None

    def calculate_type(self):
        return self.entity_instance.is_a()
    
    def get_parent(self):
        return self.parent

    def display(self):
        print(f"{self.__class__.__name__}: {self.entity_instance} ({self.guid})")
    
    def check_import(self, other, report):
        if self.guid != other.guid:
            report.add_deletion(self.guid, self.entity_type)
            report.add_addition(other.guid, self.entity_type)
            return

        if self.name != other.name:
            report.add_deletion(self.guid, self.entity_type)
            report.add_addition(self.guid, self.entity_type)


class Project(Component):
    """"
    #todo perhaps not the best to start the tree with the project
    Preference would be to have a single tree but file can contain multiple projects
    """
    def __init__(self, entity_instance, name, file):
        super().__init__(entity_instance, name)
        self.file = file
        self.sites = []
        self._init_sites()

    def _init_sites(self):
        for decomposes in self.entity_instance.IsDecomposedBy or []:
            for related_object in decomposes.RelatedObjects:
                if related_object.is_a('IfcSite'):
                    self.sites.append(Site(entity_instance = related_object,
                                        name = 'Site', 
                                        parent=self))
    
    def check_import(self, other, report):
        super().check_import(other, report) 


        original_sites = {s.guid: s for s in self.sites}
        import_sites = {s.guid: s for s in other.sites}

        for guid, storey in original_sites.items():
            if guid in import_sites:
                storey.check_import(import_sites[guid], report)
            else:
                report.add_deletion(guid, self.entity_type)

        for guid, storey in import_sites.items():
            if guid not in original_sites:
                report.add_addition(guid, self.entity_type)


class Site(Component):
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.buildings = []
        self._init_buildings()

    def _init_buildings(self):
        decomposes = self.entity_instance.IsDecomposedBy or []
        for decomposition in decomposes:
            for related_object in decomposition.RelatedObjects:
                if related_object.is_a('IfcBuilding'):
                    self.buildings.append(Building(entity_instance = related_object,
                                                   name = 'Building', 
                                                   parent=self))

    def display(self):
        print(f'Site: {self.entity_instance} ({self.guid})')
        for building in self.buildings:
            building.display()
        
    def check_import(self, other, report):
        super().check_import(other, report) 

        original_buildings = {s.guid: s for s in self.buildings}
        import_buildings = {s.guid: s for s in other.buildings}

        for guid, storey in original_buildings.items():
            if guid in import_buildings:
                storey.check_import(import_buildings[guid], report)
            else:
                report.add_deletion(guid, original_buildings[guid].entity_type)

        for guid, storey in import_buildings.items():
            if guid not in original_buildings:
                report.add_addition(guid, import_buildings[guid].entity_type)


class Building(Component):
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.storeys = []
        self._init_storeys()

    def _init_storeys(self):
        decomposes = self.entity_instance.IsDecomposedBy or []
        for decomposes in decomposes:
            for related_object in decomposes.RelatedObjects:
                if related_object.is_a('IfcBuildingStorey'):
                    self.storeys.append(Storey(entity_instance = related_object,
                                               name = related_object.Name, parent=self))
        

    def display(self):
        print(f'Building: {self.entity_instance} ({self.guid}')
        for storeys in self.storeys:
            storeys.display()
        
    def get_storey_names(self):
        return [storey.name for storey in self.storeys]


    def check_import(self, other, report):
        super().check_import(other, report) 

        original_storeys = {s.guid: s for s in self.storeys}
        import_storeys = {s.guid: s for s in other.storeys}

        for guid, storey in original_storeys.items():
            if guid in import_storeys:
                storey.check_import(import_storeys[guid], report)
            else:
                report.add_deletion(guid, original_storeys[guid].entity_type)

        for guid, storey in import_storeys.items():
            if guid not in original_storeys:
                report.add_addition(guid, import_storeys[guid].entity_type)


class Storey(Component):
    def __init__(self, entity_instance, name, parent = None):
        super().__init__(entity_instance, name, parent = None)
        self.components = {
            'IfcBeam': [],
            'IfcColumn': [],
            'IfcCovering': [],
            'IfcDistributionElement': [],
            'IfcDoor': [],
            'IfcMember': [],
            'IfcOpening': [],
            'IfcPipe': [],
            'IfcRailing': [],
            'IfcRoof': [],
            'IfcSlab': [],
            'IfcSpace': [],
            'IfcStair': [],
            'IfcWall': [],
            'IfcWindow': []
        }
        self._init_storey_elements()
        pass

    def _init_storey_elements(self):
        contains_elements = self.entity_instance.ContainsElements or []
        for contains_element in contains_elements:
            for related_element in contains_element.RelatedElements:
                for comp_type in self.components:
                    if related_element.is_a(comp_type):
                        component_class = globals().get(comp_type, None)
                        if component_class:
                            component = component_class(entity_instance=related_element,
                                                        name=related_element.Name, 
                                                        parent=self)
                            self.components[comp_type].append(component)



    def display(self):
        print(f"Storey: {self.entity_instance} ({self.guid}")

    def check_import(self, other, report):
        super().check_import(other, report)
        for comp_type, orig_components in self.components.items():
            if comp_type == 'IfcWall':
                pass
            import_components = other.components.get(comp_type, [])

            orig_guid_map = {comp.guid: comp for comp in orig_components}
            import_guid_map = {comp.guid: comp for comp in import_components}
            for guid, comp in orig_guid_map.items():
                if guid not in import_guid_map:
                    report.add_deletion(guid, comp_type)
                elif get_properties(orig_guid_map[guid].entity_instance) != get_properties(import_guid_map[guid].entity_instance):
                    report.add_modification(guid, comp_type)

            for guid, comp in import_guid_map.items():
                if guid not in orig_guid_map:
                    report.add_addition(guid, comp_type)

                elif orig_guid_map[guid].name != comp.name:
                    report.add_modification(guid, comp_type)
    


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


class ComparisonReport:
    def __init__(self):
        self.additions = []
        self.deletions = []

    def add_addition(self, guid, entity_type):
        self.additions.append({'guid' : guid, 'entity_type': entity_type})

    def add_deletion(self, guid, entity_type):
        self.deletions.append({'guid' : guid, 'entity_type': entity_type})

    def add_modification(self, guid, entity_type):
        """
        Modifications are in the style of 'git diff'; one element deleted and one added
        """
        self.add_deletion(guid, entity_type)
        self.add_addition(guid, entity_type)

    def display(self):
        for i in self.deletions:
            print(f"\033[91mDeleted: {i['guid']} ({i['entity_type']})\033[0m")  # Red text for deletions
        for i in self.additions:
            print(f"\033[92mAdded: {i['guid']} ({i['entity_type']})\033[0m")    # Green text for additions


def get_properties(element):
    def get_recursive_props(psets):
        properties = {}
        for name, value in psets.items():
            if isinstance(value, dict):
                properties[name] = get_recursive_props(value)
            else:
                properties[name] = value
        return properties
    return get_recursive_props(ifcopenshell.util.element.get_psets(element))


def run(original_fn : str, import_fn : str):
    print(f"Validating import : {import_fn}")
    report = ComparisonReport()

    original_file = ifcopenshell.open(original_fn)
    original_tree = Project(original_file.by_type('IfcProject')[0], 'Project', original_file)

    import_file = ifcopenshell.open(import_fn)
    import_tree = Project(import_file.by_type('IfcProject')[0], 'Project', file = import_file)
    



    original_tree.check_import(import_tree, report)

    report.display()

if __name__ == '__main__':
    run(original_fn = 'original_Schependomlaan (1).ifc', import_fn = 'test_files/3_schependomlaan.ifc')