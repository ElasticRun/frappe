import frappe
from frappe.frappeclient import FrappeClient
import json
from frappe.defaults import set_default

def get_remote_logs():
    sync_status = frappe.db.sql('''
		select
			defkey, defValue
		from
        			`tabDefaultValue`
		where
			defkey=%s and parent=%s
		for update''', ("client_sync_running", "__default"), as_dict = True)

    if sync_status[0]["defValue"] == "Active":
        return

    sync_pos = frappe.db.sql('''
		select
			defkey, defValue
		from
			`tabDefaultValue`
		where
			defkey=%s and parent=%s
		for update''', ("client_sync_pos", "__default"), as_dict = True)

    last_inserted_logid = sync_pos[0]["defValue"]
    print("lild", last_inserted_logid)
    current_working_logid = int(last_inserted_logid)

    # master_setup = FrappeClient(frappe.local.conf.federation_master_hostname,frappe.local.conf.federation_master_user, frappe.local.conf.federation_master_password)
    master_setup = FrappeClient(frappe.local.conf.master_node,
            frappe.local.conf.master_user,
            frappe.local.conf.master_pass)
            
    new_master_logs = master_setup.post_request({
        "cmd": "frappe.federation_master.send_new_logs",
        "name_threshold": current_working_logid,
        "limit": 100
    })
    print ("nml", new_master_logs)

    for master_log in new_master_logs:
        print("ml", master_log)
        if master_log["action"] == "INSERT":
            print("In INsert")
            original_doc = master_setup.get_doc(master_log["doctype"], master_log["docname"])
            new_doc = frappe.get_doc(original_doc)
            new_doc.name = original_doc["name"]
            new_doc.insert()
        elif master_log["action"] == "UPDATE":
            updated_doc = master_setup.get_doc(master_log["doctype"], master_log["docname"])
            original_doc = frappe.get_doc(master_log["doctype"], master_log["docname"])
            for fieldname in updated_doc.keys():
                original_doc.set(fieldname, updated_doc.get(fieldname))
            original_doc.save()
        elif master_log["action"] == "RENAME":
            frappe.rename_doc(master_log["doctype"], master_log["docname"], master_log["actiondata"])
        elif master_log["action"] == "DELETE":
            frappe.delete_doc_if_exists(master_log["doctype"], master_log["docname"])

        current_working_logid = current_working_logid + 1

    set_default("client_sync_pos", current_working_logid, "__default")
    set_default("client_sync_running", "Inactive", "__default")
