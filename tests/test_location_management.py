# -*- coding: utf-8 -*-
from test_resource_base import ActiniaResourceTestCaseBase
from flask.json import loads as json_loads, dumps as json_dumps
import unittest

__license__ = "GPLv3"
__author__     = "Sören Gebbert"
__copyright__  = "Copyright 2016, Sören Gebbert"
__maintainer__ = "Sören Gebbert"
__email__      = "soerengebbert@googlemail.com"


class LocationTestCase(ActiniaResourceTestCaseBase):

    def test_list_locations(self):
        rv = self.server.get('/locations',
                             headers=self.user_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 200, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        if "nc_spm_08" in json_loads(rv.data)["locations"]:
            location = "nc_spm_08"

        self.assertEqual(location, "nc_spm_08", "Wrong location listed")

    def test_location_info(self):
        rv = self.server.get('/locations/nc_spm_08/info',
                             headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 200, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        region_settings = json_loads(rv.data)["process_results"]["region"]
        projection_settings = json_loads(rv.data)["process_results"]["projection"]

        self.assertTrue("depths" in  region_settings)
        self.assertTrue("ewres" in  region_settings)
        self.assertTrue("cols" in  region_settings)
        self.assertTrue("rows" in  region_settings)

    def test_location_global_db_error(self):
        # ERROR: Try to create a location as admin that exists in the global database
        rv = self.server.post('/locations/nc_spm_08',
                              data=json_dumps({"epsg":"4326"}),
                              content_type="application/json",
                              headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 400, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

    def test_location_creation_and_deletion(self):

        # Delete a potentially existing location
        rv = self.server.delete('/locations/test_location',
                                headers=self.admin_auth_header)

        # Create new location as admin
        rv = self.server.post('/locations/test_location',
                              data=json_dumps({"epsg":"4326"}),
                              content_type="application/json",
                              headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 200, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        # ERROR: Try to create a location as admin that already exists
        rv = self.server.post('/locations/test_location',
                              data=json_dumps({"epsg":"4326"}),
                              content_type="application/json",
                              headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 400, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        # Delete location
        rv = self.server.delete('/locations/test_location',
                                headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 200, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        # ERROR: Delete should fail, since location does not exists
        rv = self.server.delete('/locations/test_location',
                                headers=self.admin_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 400, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

    def test_location_creation_and_deletion_as_user(self):

        # ERROR: Try to create a location as user
        rv = self.server.post('/locations/test_location_user',
                              data=json_dumps({"epsg":"4326"}),
                              content_type="application/json",
                              headers=self.user_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 401, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)

        # ERROR: Delete should fail since the user is not authorized
        rv = self.server.delete('/locations/test_location_user',
                                headers=self.user_auth_header)
        print(rv.data)
        self.assertEqual(rv.status_code, 401, "HTML status code is wrong %i"%rv.status_code)
        self.assertEqual(rv.mimetype, "application/json", "Wrong mimetype %s"%rv.mimetype)



if __name__ == '__main__':
    unittest.main()
