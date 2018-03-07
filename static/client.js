$(document).ready(function() {
    var thumb = new FileReader();
    var sender = new FileReader();
    var tgt_cst = null;
    var b64arr = [];
    thumb.addEventListener('load', function() {
        //$("#thumbnail").children("img").attr("src", thumb.result);
        if ($("#thumbnail > img").length) {
            $("#thumbnail > img").remove();
        }
        $("#thumbnail").append('<img src="'+thumb.result+'">');
        b64arr = lsplit(thumb.result, Math.floor(thumb.result.length / 10));
        console.log("b64arr length:"+b64arr.length);
        console.log("[] length:"+b64arr[0].length);
    });
    
    if (window.File && window.FileReader) {
        console.log("File API is available");
    }else{console.log("File API is NOT available");}

    namespace = '/test';
    var hostname = document.location.hostname;
    console.log("hostname:"+hostname);
    if (hostname == "localhost" || hostname == "127.0.0.1" || hostname == "") {
        var socket = io('http://127.0.0.1:5000' + namespace);
    } else {
        var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);
    }
    console.log(socket);
    
    socket.on('connect', function() {
        console.log("connect");
        $(".progressbar").val(0);
        socket.emit('my_event', {data: "Checked connection"});
    });
    socket.on('my_response', function(msg) {
        $("#log").append('<br>' + $('<div/>').text('Received: ' + msg.data).html());
    });
    socket.on('message', function() {
        console.log("message");
    });
    socket.on('return_image', function(msg) {
        console.log("image received");
        console.log(msg.data)
        //$("#result").html('<img src="'+msg.data+'">');
        if ($("#result > img").length) {
            $("#result > img").remove();
        }
        $("#result").append('<img src="'+msg.data+'">');
    });
    //分割データ受信
    socket.on('require_data', function(msg) {
        if (msg.index == b64arr.length) {
            socket.emit('data_end', {cst: tgt_cst});
            $("#log").append('<br>' + $('<div/>').text("finish sending").html());
        }else{
            $("#sendBar").val(msg.index)
            socket.emit('data_cont', {data: b64arr[msg.index], index: msg.index});
        }
    });

    socket.on('searching', function(msg){
        $("#searchBar").val(msg.data)
    });

    $('form#emit').submit(function(event) {
        console.log("pushed");
        socket.emit('my_event', {data: $('#emit_data').val()});
        return false;
    });
    $('#image_data').change(function(){
        //reader.readAsArrayBuffer(this.files[0]);
        thumb.readAsDataURL(this.files[0]);
    });
    $("form#toServer").submit(function(event) {
        if (thumb.result == null) {
            alert("画像を指定してください");
        } else if (tgt_cst == null) {
            alert("星座を指定してください"); 
        }else if (hostname.disconnected == true) {
            //うまくできない
            alert("サーバーとの接続に失敗しました\nページを再読み込みしてください");
        } else {
            $(".progressbar").val(0);
            $("#log").append('<br>' + $('<div/>').text("send").html());
            //socket.emit('my_image', {data: buf});
            socket.emit('data_start', {data: b64arr[0], index: 0});
            //socket.emit('data_end', {data: thumb.result})
        }
        return false;        
    });

    //モーダルウインドウ
    $(".openModal").click(function() {
        var navClass = $(this).attr("class"),
            href = $(this).attr("href");
            $(href).fadeIn();
        $(this).addClass("open");
        return false;
    });
    $(".overLay").click(function(){
        $(this).parents(".modal").fadeOut();
        $(".openModal").removeClass("open");
        return false;
    });
    $(".constellationList").click(function(){
        id = $(this).attr("id");
        tgt_cst = id;
        $("#selectConstellation").empty().append(
            "<img id=\"tmpConstellation\" src=\"/static/" + id + ".svg\" style=\"object-fit:contain\">");
        deSVG('#tmpConstellation', true);
        $(this).parents(".modal").fadeOut();
        $(".openModal").removeClass("open");
        return false;
    });
    $(".constellationList").hover(function() {
        $(this).children("span").fadeIn();
        $(this).children("img").animate({
            opacity: 0.5
        });
    }, function() {
        $(this).children("span").fadeOut();
        $(this).children("img").animate({
            opacity: 1
        });
    })

    //sender.html ************************************************************************
    var contentFileName;
    $("#content > #content_image").change(function() {
        sender.readAsDataURL(this.files[0]);
        contentFileName = this.files[0].name;
    });
    $("form#content").submit(function(event) {
        var text = $(this).children("#content_message").val();
       if (text == "") {
           alert("1を入力してください");
       }else{
            $(".loading").fadeIn();
            if (sender.result == undefined) {
                sender.result = null;
                contentFileName = null;
            }
            socket.emit('content_push', {content: text, file: sender.result, file_name: contentFileName});
       }
       return false;
    });
    socket.on("send_complete", function(msg){
        $(".loading").fadeOut();
        alert("メッセージが送信されました。ありがとうございます！");
    });
    
});
function lsplit(str, length) {
    var resultArr = [];
    if (!str || !length || length < 1) {
        return resultArr;
    }
    var index = 0;
    var start = index;
    var end = start + length;
    while (start < str.length) {
        resultArr[index] = str.substring(start, end);
        index++;
        start = end;
        end = start + length;
    }
    return resultArr;
}