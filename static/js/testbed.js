function TestResults(filterTermOrder) {
  this.filterTermOrder = filterTermOrder;
  this.filterTerms = {
    "backend_nodes": "Backend Nodes",
    "frontend_nodes": "Frontend Nodes",
    "testworker_nodes": "Testing Nodes",
    "simulation": "Test Script",
    "testbed_commit": "Test Code Commit",
    "testbed_git_url": "Test Code Repo",
    "subject_commit": "LDP Code Commit",
    "subject_git_url": "LDP Code Repo",
    "subject_docker_name": "LDP Docker Name",
    "subject_docker_tag": "LDP Docker Tag",
    "jms_use_queue": "JMS Events Enabled",
    "cassandra_replication_factor": "C* Replication",
    "cassandra_binary_read_consistency": "C* Binary Read Consistency",
    "cassandra_binary_write_consistency": "C* Binary Write Consistency",
    "cassandra_rdf_write_consistency": "C* RDF Read Consistency",
    "cassandra_rdf_read_consistency": "C* RDF Write Consistency",
    "cassandra_max_chunk_size": "C* Max Chunk Size"
  };
  this.activeFilters = {};
}

$.delete = function(url, data, callback, type){

  if ( $.isFunction(data) ){
    type = type || callback,
        callback = data,
        data = {}
  }

  return $.ajax({
    url: url,
    type: 'DELETE',
    success: callback,
    data: data,
    contentType: type
  });
}

function get(obj, searchterm) {
  var value = "n/a";
  if (searchterm in obj && obj[searchterm]['buckets'].length > 0) value = obj[searchterm]['buckets'][0]['key'];
  return value;
}

function copyToClipboard(text) {
    var $temp = $("<input>");
    $("body").append($temp);
    $temp.val(text).select();
    document.execCommand("copy");
    $temp.remove();
}

TestResults.prototype.buildTable = function() {
  var me = this;
  var data;
  var snapshots = {};
  $.when(
    $.ajax( "/sims", {
      method: "POST",
      data: JSON.stringify(this.activeFilters),
      contentType: "application/json; charset=utf-8",
      dataType: "json",
      success: function(simdata) { data = simdata; },
      failure: function(errMsg) { console.log(errMsg); }
    } ),
    $.getJSON("/list_snapshots", function(snapdata) {
      for(var snap of snapdata) {
        snapshots[snap['name']]=snap['key'];
      }
    })
  ).then(function() {
    var div = $('#testresults');
    div.empty();
    var filters = $('<ul></ul>');
    filters.appendTo(div);
    var table = $('<table class="results table table-striped"></table>');
    table.appendTo(div);
    var th = "<thead><tr>";
    th += "<th class='rotate'><div><span>Dashboard</span></div></th>";
    th += "<th class='rotate'><div><span>Date</span></div></th>";
    me.filterTermOrder.forEach(function(t) {
      var label = me.filterTerms[t];
      th += "<th data-term='"+t+"' class='term rotate'><div><span>"+label+"</span></div></th>";
    });
    th += "<th class='rotate'><div><span>OK</span></div></th>";
    th += "<th class='rotate'><div><span>KO</span></div></th>";
    th += "<th class='rotate'><div><span>Avg</span></div></th>";
    th += "<th class='rotate'><div><span>Max</span></div></th>";
    th += "<th class='rotate'><div><span>Min</span></div></th>";
    th += "</tr></thead>";
    $(th).appendTo(table);
    tbody = $('<tbody></tbody>');
    tbody.appendTo(table);
    $.each(data, function (index, obj) {
      var name = obj['key'];
      var sim = get(obj, 'simulation');
      var to_ts = obj['Requests']['last_ts']['value'] + 60000;
      var from_ts = obj['Requests']['first_ts']['value'] - 60000;
      var time = obj['Requests']['first_ts']['value'];
      var dt = new Date();
      dt.setTime(time);
      var ok = 0;
      var ko = 0;
      for(var st of obj.Requests.status.buckets) {
          if(st.key == "OK") {
            ok = st.doc_count;
          } else if (st.key == "KO") {
            ko = st.doc_count;
          }
      }
      var count = Math.round(obj['Requests']['req_duration_stats']['count']);
      var avg = Math.round(obj['Requests']['req_duration_stats']['avg']);
      var max = Math.round(obj['Requests']['req_duration_stats']['max']);
      var min = Math.round(obj['Requests']['req_duration_stats']['min']);
      var grafana_link = `http://drastic-testbed.umd.edu:3000/d/MwnPtQfiz/ldp-performance-test-dashboard?orgId=1&from=${from_ts}&to=${to_ts}`;

      let el = "<tr>";

      let snapshot_link = null;
      if(name in snapshots) {
        snapshot_key = snapshots[name];
        snapshot_link = `http://drastic-testbed.umd.edu:3000/dashboard/snapshot/${snapshot_key}`;
      }
      let code_link = get(obj, "subject_git_url");
      if(code_link.startsWith("git@")) {
        code_link = code_link.replace(":","/");
        code_link = code_link.substring(4, code_link.length);
        code_link = "https://" + code_link;
        code_link = code_link.substring(0, code_link.length - 4);
      }
      code_link += "/commit/";
      let commit = get(obj, "subject_commit");
      let regex = /.*\-.*\-\d\.\d\-\d+\-(.*)\-?.*/;
      let matches = commit.match(regex);
      if(matches !== null && matches.length > 0) {
        commit = matches[1];
      }
      let dirt = "-dirty";
      if(commit.endsWith(dirt)) {
        commit = commit.substring(0, commit.length - dirt.length);
      }
      code_link += commit;


      el += "<td>";
      if(snapshot_link != null) {
        el += "<a title='Grafana snapshot (public)' href='"+snapshot_link+"'><img height='35px' width='35px' src='/static/graph-icon.png'/></a> ";
      } else {
        el += "<a title='Grafana dashboard (private)' href='"+grafana_link+"'>panel</a><br />";
        el += "<a class='delidx' data-name='"+name+"'>del index</a><br />";
        el += "<a class='copyidx' data-name='"+name+"'>index name</a>";
      }
      el += "<br /><a title='Link to Code commit in repository' href='"+code_link+"'>commit</a>";
      el += "</td>";

      dateStr = dt.getFullYear() + '-' +
        ('0' + (dt.getMonth()+1)).slice(-2) + '-' +
        ('0' + dt.getDate()).slice(-2);
      el += "<td>"+dateStr+"</td>";

      // Gather ye sim aggregate term values.
      for(var t of me.filterTermOrder) {
        var value = get(obj, t);
        el += "<td data-term='"+t+"' data-value='"+value+"' class='term'>"+value+"</td>";
      }

      el += "<td>"+ok+"</td>";
      el += "<td>"+ko+"</td>";
      el += "<td>"+avg+"</td>";
      el += "<td>"+max+"</td>";
      el += "<td>"+min+"</td>";

      el += "</tr>";
      $(el).appendTo(tbody);

      // Add filter term/value when clicked
      $('td.term').off().click(function(e) {
        var t = $(this).data("term");
        var v = $(this).data("value");
        me.activeFilters[t] = v;
        me.buildTable();
        return false;
      });
    });
    // Allow removal of a filter term/value
    filters.empty();
    me.filterTermOrder.forEach(function(t) {
      if(t in me.activeFilters) {
        $("<li data-term='"+t+"'>"+me.filterTerms[t]+": '"+me.activeFilters[t]+"'</li>").off().click(function(e) {
          var term = $(this).data("term");
          delete me.activeFilters[term];
          me.buildTable();
          return false;
        }).appendTo(filters);
      }
    });
    $('a.delidx').off().click(function(e) {
      var name = $(this).data("name");
      var text = "curl -XDELETE http://localhost:9200/"+name;
      copyToClipboard(text);
      return false;
    });
    $('a.copyidx').off().click(function(e) {
      var name = $(this).data("name");
      copyToClipboard(name);
      return false;
    });

    var dtable = table.DataTable({
      paging: false,
      searching: false,
      scrollY: '400px',
      order: [[1, 'desc']]
    });
  });
};
