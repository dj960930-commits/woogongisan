package com.woogong.app
import org.junit.Assert.*
import org.junit.Test
class SignalEndpointTest {
 @Test fun repositoryUrlConvertsToPages(){assertEquals("https://dj960930-commits.github.io/woogongisan",SignalEndpoint.normalize("https://github.com/dj960930-commits/woogongisan/"))}
 @Test fun pagesSubdirectoryIsPreserved(){assertEquals("https://dj960930-commits.github.io/woogongisan",SignalEndpoint.normalize(" https://dj960930-commits.github.io/woogongisan/ "))}
 @Test fun credentialsAndNonHttpsCannotBeSaved(){for(url in listOf("http://example.com","https://user:secret@example.com","https://example.com?token=secret","https://example.com#secret")){try{SignalEndpoint.normalize(url);fail(url)}catch(_:IllegalArgumentException){}}}
}
