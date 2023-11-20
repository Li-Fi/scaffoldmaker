import unittest

from cmlibs.utils.zinc.finiteelement import evaluateFieldNodesetRange
from cmlibs.utils.zinc.general import ChangeManager
from cmlibs.utils.zinc.group import identifier_ranges_to_string, mesh_group_add_identifier_ranges, \
    mesh_group_to_identifier_ranges
from cmlibs.zinc.context import Context
from cmlibs.zinc.element import Element
from cmlibs.zinc.field import Field
from cmlibs.zinc.node import Node
from cmlibs.zinc.result import RESULT_OK
from scaffoldmaker.meshtypes.meshtype_1d_network_layout1 import MeshType_1d_network_layout1
from scaffoldmaker.meshtypes.meshtype_2d_tubenetwork1 import MeshType_2d_tubenetwork1
from scaffoldmaker.meshtypes.meshtype_3d_tubenetwork1 import MeshType_3d_tubenetwork1
from scaffoldmaker.scaffoldpackage import ScaffoldPackage
from scaffoldmaker.utils.zinc_utils import get_nodeset_path_ordered_field_parameters

from testutils import assertAlmostEqualList


class NetworkScaffoldTestCase(unittest.TestCase):

    def test_network_layout(self):
        """
        Test creation of network layout scaffold.
        """
        scaffold = MeshType_1d_network_layout1
        options = scaffold.getDefaultOptions()
        self.assertEqual(3, len(options))
        self.assertEqual("1-2", options.get("Structure"))
        options["Structure"] = "1-2-3,3-4,3.2-5"

        context = Context("Test")
        region = context.getDefaultRegion()
        self.assertTrue(region.isValid())
        annotationGroups, networkMesh = scaffold.generateBaseMesh(region, options)
        self.assertEqual(0, len(annotationGroups))

        fieldmodule = region.getFieldmodule()
        mesh1d = fieldmodule.findMeshByDimension(1)
        self.assertEqual(4, mesh1d.getSize())
        nodes = fieldmodule.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
        self.assertEqual(5, nodes.getSize())
        coordinates = fieldmodule.findFieldByName("coordinates").castFiniteElement()
        self.assertTrue(coordinates.isValid())

        interactiveFunctions = scaffold.getInteractiveFunctions()
        functionOptions = None
        for interactiveFunction in interactiveFunctions:
            if interactiveFunction[0] == "Smooth derivatives...":
                functionOptions = interactiveFunction[1]
                break
        functionOptions["Update directions"] = True
        scaffold.smoothDerivatives(region, options, None, functionOptions, "meshEdits")

        minimums, maximums = evaluateFieldNodesetRange(coordinates, nodes)
        assertAlmostEqualList(self, minimums, [0.0, -0.25, 0.0], 1.0E-6)
        assertAlmostEqualList(self, maximums, [3.0, 0.25, 0.0], 1.0E-6)

        networkSegments = networkMesh.getNetworkSegments()
        self.assertEqual(3, len(networkSegments))
        self.assertEqual([1, 2, 3], networkSegments[0].getNodeIdentifiers())
        self.assertEqual([1, 1, 1], networkSegments[0].getNodeVersions())
        self.assertEqual([3, 4], networkSegments[1].getNodeIdentifiers())
        self.assertEqual([1, 1], networkSegments[1].getNodeVersions())
        self.assertEqual([3, 5], networkSegments[2].getNodeIdentifiers())
        self.assertEqual([2, 1], networkSegments[2].getNodeVersions())

        # get path parameters with versions
        nx, nd1 = get_nodeset_path_ordered_field_parameters(
            nodes, coordinates, [Node.VALUE_LABEL_VALUE, Node.VALUE_LABEL_D_DS1],
            networkSegments[2].getNodeIdentifiers(), networkSegments[2].getNodeVersions())
        self.assertEqual(2, len(nx))
        assertAlmostEqualList(self, nx[0], [2.0, 0.0, 0.0], 1.0E-6)
        assertAlmostEqualList(self, nx[1], [3.0, 0.25, 0.0], 1.0E-6)
        expected_nd = [nx[1][c] - nx[0][c] for c in range(3)]
        assertAlmostEqualList(self, nd1[0], expected_nd, 1.0E-6)
        assertAlmostEqualList(self, nd1[1], expected_nd, 1.0E-6)

    def test_2d_tube_network_sphere_cube(self):
        """
        Test sphere cube is generated correctly.
        """
        scaffoldPackage = ScaffoldPackage(MeshType_2d_tubenetwork1, defaultParameterSetName="Sphere cube")
        settings = scaffoldPackage.getScaffoldSettings()
        networkLayoutScaffoldPackage = settings["Network layout"]
        networkLayoutSettings = networkLayoutScaffoldPackage.getScaffoldSettings()
        self.assertFalse(networkLayoutSettings["Define inner coordinates"])
        self.assertEqual(4, len(settings))
        self.assertEqual(8, settings["Elements count around"])
        self.assertEqual(2.0, settings["Target element aspect ratio"])
        self.assertTrue(settings["Serendipity"])

        context = Context("Test")
        region = context.getDefaultRegion()

        # add a user-defined annotation group to network layout. Must generate first
        tmpRegion = region.createRegion()
        tmpFieldmodule = tmpRegion.getFieldmodule()
        networkLayoutScaffoldPackage.generate(tmpRegion)

        annotationGroup1 = networkLayoutScaffoldPackage.createUserAnnotationGroup(('bob', 'BOB:1'))
        group = annotationGroup1.getGroup()
        mesh1d = tmpFieldmodule.findMeshByDimension(1)
        meshGroup = group.createMeshGroup(mesh1d)
        mesh_group_add_identifier_ranges(meshGroup, [[1, 1], [5, 5]])
        self.assertEqual(2, meshGroup.getSize())
        self.assertEqual(1, annotationGroup1.getDimension())
        identifier_ranges_string = identifier_ranges_to_string(mesh_group_to_identifier_ranges(meshGroup))
        self.assertEqual('1,5', identifier_ranges_string)
        networkLayoutScaffoldPackage.updateUserAnnotationGroups()

        self.assertTrue(region.isValid())
        scaffoldPackage.generate(region)
        annotationGroups = scaffoldPackage.getAnnotationGroups()
        self.assertEqual(1, len(annotationGroups))

        fieldmodule = region.getFieldmodule()
        self.assertEqual(RESULT_OK, fieldmodule.defineAllFaces())
        mesh2d = fieldmodule.findMeshByDimension(2)
        self.assertEqual(32 * 12, mesh2d.getSize())
        mesh1d = fieldmodule.findMeshByDimension(1)
        self.assertEqual(8 * 7 * 12 + 4 * 3 * 8, mesh1d.getSize())
        nodes = fieldmodule.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
        self.assertEqual(8 * 3 * 12 + (2 + 3 * 3) * 8, nodes.getSize())
        coordinates = fieldmodule.findFieldByName("coordinates").castFiniteElement()
        self.assertTrue(coordinates.isValid())

        # check annotation group transferred to 2D tube
        annotationGroup = annotationGroups[0]
        self.assertEqual("bob", annotationGroup.getName())
        self.assertEqual("BOB:1", annotationGroup.getId())
        self.assertEqual(64, annotationGroup.getMeshGroup(fieldmodule.findMeshByDimension(2)).getSize())

        minimums, maximums = evaluateFieldNodesetRange(coordinates, nodes)
        assertAlmostEqualList(self, minimums, [-0.5682760261793237, -0.5810707177223273, -0.5933654189390684], 1.0E-8)
        assertAlmostEqualList(self, maximums, [0.5674640763685259, 0.5876184768140706, 0.5933227142314541], 1.0E-8)

        with ChangeManager(fieldmodule):
            one = fieldmodule.createFieldConstant(1.0)
            surfaceAreaField = fieldmodule.createFieldMeshIntegral(one, coordinates, mesh2d)
            surfaceAreaField.setNumbersOfPoints(4)
            fieldcache = fieldmodule.createFieldcache()
            result, surfaceArea = surfaceAreaField.evaluateReal(fieldcache, 1)
            self.assertEqual(result, RESULT_OK)
            self.assertAlmostEqual(surfaceArea, 3.974619168265453, delta=1.0E-8)

    def test_3d_tube_network_sphere_cube(self):
        """
        Test sphere cube 3-D tube network is generated correctly.
        """
        scaffoldPackage = ScaffoldPackage(MeshType_3d_tubenetwork1, defaultParameterSetName="Sphere cube")
        settings = scaffoldPackage.getScaffoldSettings()
        networkLayoutScaffoldPackage = settings["Network layout"]
        networkLayoutSettings = networkLayoutScaffoldPackage.getScaffoldSettings()
        self.assertTrue(networkLayoutSettings["Define inner coordinates"])
        self.assertEqual(5, len(settings))
        self.assertEqual(8, settings["Elements count around"])
        self.assertEqual(1, settings["Elements count through wall"])
        self.assertEqual(2.0, settings["Target element aspect ratio"])
        self.assertTrue(settings["Serendipity"])
        settings["Elements count through wall"] = 2

        context = Context("Test")
        region = context.getDefaultRegion()

        # set custom inner coordinates
        tmpRegion = region.createRegion()
        networkLayoutScaffoldPackage.generate(tmpRegion)
        networkMesh = networkLayoutScaffoldPackage.getConstructionObject()
        functionOptions = {
            "Mode": {"Wall proportion": True, "Wall thickness": False},
            "Value": 0.2}
        editGroupName = "meshEdits"
        MeshType_1d_network_layout1.assignInnerCoordinates(tmpRegion, networkLayoutSettings, networkMesh,
                                                           functionOptions, editGroupName=editGroupName)
        # put edited coordinates into scaffold package
        sir = tmpRegion.createStreaminformationRegion()
        srm = sir.createStreamresourceMemory()
        sir.setResourceGroupName(srm, editGroupName)
        sir.setResourceFieldNames(srm, ["coordinates", "inner coordinates"])
        tmpRegion.write(sir)
        result, meshEditsString = srm.getBuffer()
        self.assertEqual(RESULT_OK, result)
        networkLayoutScaffoldPackage.setMeshEdits(meshEditsString)

        self.assertTrue(region.isValid())
        scaffoldPackage.generate(region)

        fieldmodule = region.getFieldmodule()
        self.assertEqual(RESULT_OK, fieldmodule.defineAllFaces())
        mesh3d = fieldmodule.findMeshByDimension(3)
        self.assertEqual(32 * 12 * 2, mesh3d.getSize())
        nodes = fieldmodule.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
        self.assertEqual(8 * 3 * 12 * 3 + (2 + 3 * 3) * 8 * 3, nodes.getSize())
        coordinates = fieldmodule.findFieldByName("coordinates").castFiniteElement()
        self.assertTrue(coordinates.isValid())

        minimums, maximums = evaluateFieldNodesetRange(coordinates, nodes)
        assertAlmostEqualList(self, minimums, [-0.5682760261793237, -0.5810707177223273, -0.5933654189390684], 1.0E-8)
        assertAlmostEqualList(self, maximums, [0.5674640763685259, 0.5876184768140706, 0.5933227142314541], 1.0E-8)

        with ChangeManager(fieldmodule):
            one = fieldmodule.createFieldConstant(1.0)
            isExterior = fieldmodule.createFieldIsExterior()
            isExteriorXi3_0 = fieldmodule.createFieldAnd(
                isExterior, fieldmodule.createFieldIsOnFace(Element.FACE_TYPE_XI3_0))
            isExteriorXi3_1 = fieldmodule.createFieldAnd(
                isExterior, fieldmodule.createFieldIsOnFace(Element.FACE_TYPE_XI3_1))
            mesh2d = fieldmodule.findMeshByDimension(2)
            fieldcache = fieldmodule.createFieldcache()

            volumeField = fieldmodule.createFieldMeshIntegral(one, coordinates, mesh3d)
            volumeField.setNumbersOfPoints(4)
            result, volume = volumeField.evaluateReal(fieldcache, 1)
            self.assertEqual(result, RESULT_OK)
            self.assertAlmostEqual(volume, 0.07062041904759, delta=1.0E-8)

            outerSurfaceAreaField = fieldmodule.createFieldMeshIntegral(isExteriorXi3_1, coordinates, mesh2d)
            outerSurfaceAreaField.setNumbersOfPoints(4)
            result, outerSurfaceArea = outerSurfaceAreaField.evaluateReal(fieldcache, 1)
            self.assertEqual(result, RESULT_OK)
            self.assertAlmostEqual(outerSurfaceArea, 3.974619168265453, delta=1.0E-8)

            innerSurfaceAreaField = fieldmodule.createFieldMeshIntegral(isExteriorXi3_0, coordinates, mesh2d)
            innerSurfaceAreaField.setNumbersOfPoints(4)
            result, innerSurfaceArea = innerSurfaceAreaField.evaluateReal(fieldcache, 1)
            self.assertEqual(result, RESULT_OK)
            self.assertAlmostEqual(innerSurfaceArea, 3.299211421181769, delta=1.0E-8)



if __name__ == "__main__":
    unittest.main()
