from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import ifcopenshell
from ifcopenshell.file import file as IfcFile
from ifcopenshell.entity_instance import entity_instance as IfcEntity


class Component(ABC):
    def __init__(self, entity_instance, name, parent = None):
        self.entity_instance = entity_instance
        self.name = name
        self.parent = parent
        self.entity_name = self.calculate_entity_name()
        self.guid = self.calculate_guid()
        
    def calculate_entity_name(self):
        # Logic to extract name from entity
        return self.entity_instance.Name if hasattr(self.entity_instance, 'Name') else None

    def calculate_guid(self):
        # Logic to extract GUID from entity
        return self.entity_instance.GlobalId if hasattr(self.entity_instance, 'GlobalId') else None
    
    def get_parent(self):
        return self.parent

    def display(self):
        print(f"{self.__class__.__name__}: {self.entity_instance} ({self.guid})")
    
    def check_import(self, other, report):
        if self.guid != other.guid:
            report.add_discrepancy(f"Different GUID: {self.guid} vs {other.guid}")
        if self.name != other.name:
            report.add_discrepancy(f"Different name: {self.name} vs {other.name}")

class Project(Component):
    def __init__(self, entity_instance, name):
        super().__init__(entity_instance, name)
        self.sites = []
        self._init_sites()

    def _init_sites(self):
            decomposes = self.entity_instance.IsDecomposedBy or []
            for related_object in decomposes.RelatedObjects:
                if related_object.is_a('IfcSite'):
                    self.sites.append(Site(entity_instance = related_object,
                                        name = 'Site', 
                                        parent=self))


class Site(Component):
    def __init__(self, entity_instance, name):
        super().__init__(entity_instance, name)
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
        if len(self.buildings) != len(other.buildings):
            report.add_discrepancy(f"Different number of buildings in site {self.guid}")
        for self_building, other_building in zip(self.buildings, other.buildings):
            if self_building.guid != other_building.guid or self_building.name != other_building.name:
                report.add_discrepancy(f"Mismatch in building details for site {self.guid}")
            self_building.check_import(other_building, report)


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
        for storey, other_storey in zip(self.storeys, other.storeys):
             storey.check_import(other_storey, report)

        if len(self.storeys) != len(other.storeys):
            report.add_discrepancy(f"Different number of storeys in building {self.guid}")

        for self_storey, other_storey in zip(self.storeys, other.storeys):
            if self_storey.guid != other_storey.guid or self_storey.name != other_storey.name:
                report.add_discrepancy(f"Mismatch in storey details for building {self.guid}")
            self_storey.check_import(other_storey, report)


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
            'IfcObject': [],
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

    def _init_storey_elements(self):
        contains_elements = self.entity_instance.ContainsElements or []
        for contains_element in contains_elements:
            for related_element in contains_element.RelatedElements:
                entity_type = related_element.is_a()
                component_class = globals().get(entity_type, None)
                if component_class and entity_type in self.components:
                    component = component_class(entity_instance=related_element,
                                                name=related_element.Name, 
                                                parent=self)
                    self.components[entity_type].append(component)

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

class Ifctair(Component):
        pass

class IfcWall(Component):
        pass

class IfcWindow(Component):
        pass


class ComparisonReport():
    def __init__(self):
          self.discrepancies = []
        
    def add_discrepancy(self, discrepancy):
        self.discrepancies.append(discrepancy)
    
    def display(self):
         for discrepancy in self.discrepancies:
            print(discrepancy)

original_file = ifcopenshell.open('original_Schependomlaan (1).ifc')
original_tree = Site(original_file.by_type('IfcSite')[0], 'Site')


import_file = ifcopenshell.open('import_Schependomlaan.ifc')
import_tree = Site(import_file.by_type('IfcSite')[0], 'Site')


def generate_import_validation(original_tree, import_tree):
    report = ComparisonReport()
    import_projects = import_file.by_type("IfcProject")
    if len(import_projects) > 1:
        discrepancies = [f"project {project} is incorrectly added and no decomposition" 
                        for project in import_projects if not project.IsDecomposedBy]
        for discrepancy in discrepancies:
            report.add_discrepancy(discrepancy)
    original_tree.check_import(import_tree, report)

    return report

report = generate_import_validation(original_tree, import_tree)
import pdb; pdb.set_trace()