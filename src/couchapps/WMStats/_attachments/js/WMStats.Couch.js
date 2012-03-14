/*
 * Define Global values for couch db and couch db function
 * this has dependency on jquery.js and jquery.couch.js
 */
WMStats.namespace("Couch")

WMStats.Couch = (function(){
    // couchdb name for central summary db
    var _dbName = "wmstats";
    // couchapp name
    var _Design = "WMStats";
    var _couchDB = $.couch.db(_dbName);
    
    function _combineOption(options, callback) {
        //combine options and callbacks for jquery.couch.js
        //TODO need to extend not just for success. (i.e failed case)
        var options = options || {};
        options.success = callback;
        return options
    }
    function view(name, options, callback){
        return _couchDB.view(_Design +"/" + name, 
                             _combineOption(options, callback));
    }
    
    function allDocs(options, callback){
        return _couchDB.allDocs(_combineOption(options, callback));
    }
    
    return {'view': view, "allDocs": allDocs};
})()
